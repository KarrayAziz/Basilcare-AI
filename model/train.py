"""Train the leaf-screening classifier by transfer learning from MobileNetV3-Small.

    python model/train.py --data dataset/split --out model/runs/leafscreen-0.1

Why MobileNetV3-Small: designed for phone CPUs, about 1 M parameters at 224 px, and every
layer quantizes to int8, which is what the Raspberry Pi 4 runs fastest (scope section 5.1,
risk "edge inference too slow").

Two phases:
1. the ImageNet backbone is frozen and only the new classification head learns;
2. the last backbone layers are unfrozen and fine-tuned with a 10x lower learning rate.
Early stopping on the validation loss keeps the best epoch. Classes are weighted by their
inverse frequency, so a rare "stressed" class is not ignored.

Pre-processing matches the Pi exactly: centre square crop, resize, RGB 0..255 into the
model (MobileNetV3 rescales internally). Augmentation (flips, rotation, zoom, brightness,
contrast) runs in the input pipeline only, so the exported model contains no random layers.

Outputs in --out: best.keras, labels.json, history.json, training.json (all settings).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
import keras


def datasets(data, size, batch, seed):
    common = dict(image_size=(size, size), batch_size=batch, label_mode="int", crop_to_aspect_ratio=True,
                  seed=seed)
    train = keras.utils.image_dataset_from_directory(data / "train", shuffle=True, **common)
    val = keras.utils.image_dataset_from_directory(data / "val", shuffle=False, **common)
    return train, val, train.class_names


def augmenter(seed):
    return keras.Sequential([
        keras.layers.RandomFlip("horizontal_and_vertical", seed=seed),
        keras.layers.RandomRotation(0.1, seed=seed),
        keras.layers.RandomZoom(0.15, seed=seed),
        keras.layers.RandomBrightness(0.15, value_range=(0, 255), seed=seed),
        keras.layers.RandomContrast(0.15, seed=seed),
    ], name="augmentation")


def class_weights(train, n_classes):
    counts = np.zeros(n_classes)
    for _, labels in train.unbatch():
        counts[int(labels)] += 1
    total = counts.sum()
    return {i: float(total / (n_classes * c)) if c else 1.0 for i, c in enumerate(counts)}, counts.tolist()


def build(n_classes, size, weights, dropout, minimalistic=True):
    # minimalistic=True: no hard-swish, no squeeze-excite, 3x3 kernels only. Those layers quantize
    # badly to int8: with the full variant, the int8 export of a model at 100 % float accuracy gave
    # inverted predictions (5.6 %), and XNNPACK refused its int8 MEAN ops. The minimalistic
    # variant was designed by its authors for quantized, CPU-only deployment.
    backbone = keras.applications.MobileNetV3Small(
        input_shape=(size, size, 3), include_top=False, pooling="avg", minimalistic=minimalistic,
        weights=None if weights == "none" else weights, include_preprocessing=True)
    backbone.trainable = False
    inputs = keras.Input((size, size, 3), name="pixels")          # RGB, 0..255
    x = backbone(inputs, training=False)
    x = keras.layers.Dropout(dropout)(x)
    outputs = keras.layers.Dense(n_classes, activation="softmax", name="scores")(x)
    return keras.Model(inputs, outputs, name="leafscreen"), backbone


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path, help="output of prepare_dataset.py")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--size", type=int, default=224, help="input size in pixels (96, 128, 160, 192, 224)")
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=20, help="head-only epochs (phase 1)")
    parser.add_argument("--fine-tune-epochs", type=int, default=10, help="phase 2; 0 to skip")
    parser.add_argument("--unfreeze", type=int, default=30, help="backbone layers unfrozen in phase 2")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--weights", default="imagenet", help="imagenet, or none (smoke tests only)")
    parser.add_argument("--full-variant", action="store_true",
                        help="full MobileNetV3-Small (hard-swish, squeeze-excite) instead of the minimalistic "
                             "one; only if you deploy the float model, it does not survive int8 quantization")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    keras.utils.set_random_seed(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    train, val, labels = datasets(args.data, args.size, args.batch, args.seed)
    weights, counts = class_weights(train, len(labels))
    print("classes:", dict(zip(labels, counts)), "weights:", weights)

    augment = augmenter(args.seed)
    train = train.map(lambda x, y: (augment(x, training=True), y), num_parallel_calls=tf.data.AUTOTUNE)
    train = train.prefetch(tf.data.AUTOTUNE)
    val = val.prefetch(tf.data.AUTOTUNE)

    model, backbone = build(len(labels), args.size, args.weights, args.dropout, not args.full_variant)
    best = args.out / "best.keras"
    callbacks = [
        keras.callbacks.ModelCheckpoint(best, monitor="val_loss", save_best_only=True),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
    ]
    model.compile(keras.optimizers.Adam(args.lr), "sparse_categorical_crossentropy", metrics=["accuracy"])
    start = time.time()
    history = model.fit(train, validation_data=val, epochs=args.epochs, class_weight=weights,
                        callbacks=callbacks, verbose=2).history

    if args.fine_tune_epochs > 0:
        backbone.trainable = True
        for layer in backbone.layers[:-args.unfreeze]:
            layer.trainable = False
        for layer in backbone.layers:   # keep BatchNorm statistics frozen: small datasets
            if isinstance(layer, keras.layers.BatchNormalization):
                layer.trainable = False
        model.compile(keras.optimizers.Adam(args.lr / 10), "sparse_categorical_crossentropy", metrics=["accuracy"])
        fine = model.fit(train, validation_data=val, epochs=args.fine_tune_epochs, class_weight=weights,
                         callbacks=callbacks, verbose=2).history
        for key, values in fine.items():
            history.setdefault(key, []).extend(values)

    if not best.exists():   # e.g. val_loss never finite: keep the last weights anyway
        model.save(best)
    (args.out / "labels.json").write_text(json.dumps(labels))
    (args.out / "history.json").write_text(json.dumps({k: [float(v) for v in vs] for k, vs in history.items()}))
    settings = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    settings.update(labels=labels, train_counts=counts, seconds=round(time.time() - start),
                    best_val_loss=float(min(history["val_loss"])),
                    best_val_accuracy=float(max(history["val_accuracy"])),
                    tensorflow=tf.__version__)
    (args.out / "training.json").write_text(json.dumps(settings, indent=2))
    print(f"saved {best} (best val accuracy {settings['best_val_accuracy']:.3f})")


if __name__ == "__main__":
    main()
