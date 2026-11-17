"""Convert a trained model to TensorFlow Lite for the Raspberry Pi.

    python iot/ai/model/export_tflite.py --run iot/ai/model/runs/leafscreen-0.1 --data dataset/split --version 0.1

Writes to iot/ai/model/export/ (or --out):
  leafscreen-<version>-int8.tflite   full-integer model: int8 input and output. Fastest on the
                                     Pi 4 CPU and about 4x smaller than float32.
  leafscreen-<version>-float.tflite  float32 reference, to measure what quantization costs.
  one .json sidecar per model: version, labels, input size. iot/edge/basilcare_edge/inference.py
  reads it, and the version goes into every screening message (scope section 5.4 traceability).

int8 quantization needs a "representative dataset" to calibrate the value ranges: a few
hundred TRAINING pictures, never test pictures (that would leak the test set into the model).
"""
import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf
import keras


def representative(data, size, limit):
    files = sorted(p for p in (data / "train").rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})
    rng = np.random.default_rng(0)
    rng.shuffle(files)
    for path in files[:limit]:
        image = keras.utils.load_img(path)
        side = min(image.size)
        left, top = (image.width - side) // 2, (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side)).resize((size, size))
        yield [np.asarray(image, dtype=np.float32)[np.newaxis, ...]]


def convert(saved_model, int8, data=None, size=None, samples=200):
    converter = tf.lite.TFLiteConverter.from_saved_model(str(saved_model))
    if int8:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = lambda: representative(data, size, samples)
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
    return converter.convert()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, type=Path, help="folder written by train.py")
    parser.add_argument("--data", required=True, type=Path, help="dataset split (train/ is used for calibration)")
    parser.add_argument("--version", required=True, help="e.g. 0.1; becomes leafscreen-0.1-int8")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "export")
    parser.add_argument("--samples", type=int, default=200, help="calibration pictures for int8")
    args = parser.parse_args(argv)

    model = keras.models.load_model(args.run / "best.keras")
    labels = json.loads((args.run / "labels.json").read_text())
    size = int(model.input_shape[1])
    args.out.mkdir(parents=True, exist_ok=True)
    training = json.loads((args.run / "training.json").read_text()) if (args.run / "training.json").exists() else {}

    with tempfile.TemporaryDirectory() as folder:
        saved = Path(folder) / "saved_model"
        model.export(str(saved))          # Keras 3: SavedModel first, then the TFLite converter
        for kind in ("int8", "float"):
            name = f"leafscreen-{args.version}-{kind}"
            blob = convert(saved, kind == "int8", args.data, size, args.samples)
            (args.out / f"{name}.tflite").write_bytes(blob)
            metadata = {
                "version": name,
                "labels": labels,
                "input_size": size,
                "input": "RGB 0..255, centre square crop",
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "training": {k: training.get(k) for k in ("best_val_accuracy", "train_counts", "weights", "epochs")},
            }
            (args.out / f"{name}.json").write_text(json.dumps(metadata, indent=2))
            print(f"{name}.tflite: {len(blob) / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
