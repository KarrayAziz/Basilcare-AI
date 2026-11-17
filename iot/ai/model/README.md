# model

Training, export and evaluation of the **leaf-screening model** that runs on the Raspberry Pi (scope §5.1, §5.4). The model screens a leaf picture for visible abnormalities. It is **not a diagnosis**: on the Pi, a result is flagged `review_required` whenever the model is unsure or the picture is poor.

```
pictures ─► prepare_dataset.py ─► train.py ─► export_tflite.py ─► evaluate.py ─► iot/edge/ config.toml [model] path
(per class)   dedupe, quality,     MobileNetV3   int8 + float       held-out test,     the Pi loads the .tflite
              70/15/15 split       transfer      .tflite + .json    confusion matrix   and its .json sidecar
```

## What each script does

| Script | Output |
|---|---|
| [`prepare_dataset.py`](prepare_dataset.py) | `split/{train,val,test}/<class>/`, `manifest.csv` (file, class, split, sha256), `audit.json`. Removes exact duplicates so no picture is in both train and test. Optionally drops pictures that fail the Pi's quality checks (`--drop-poor-quality`). Warns when a class has fewer than 30 pictures. |
| [`train.py`](train.py) | `runs/<name>/best.keras`, `labels.json`, `history.json`, `training.json`. Transfer learning from **MobileNetV3-Small (minimalistic)** with ImageNet weights: the head first, then fine-tuning of the last layers. Uses class weights and early stopping. |
| [`export_tflite.py`](export_tflite.py) | `export/leafscreen-<version>-int8.tflite` and `-float.tflite`, each with a `.json` sidecar (version, labels, input size). The version is written into every screening message, for traceability (scope §5.4). |
| [`evaluate.py`](evaluate.py) | Confusion matrix, per-class precision, recall and F1, and accuracy on the **held-out test set**. Also reports how many results pass the review threshold and how accurate those are. Uses the Pi's own inference code (`iot/edge/basilcare_edge/inference.py`), so the numbers include quantization. |

## Why it is organised this way

- **Pre-processing is identical on the PC and the Pi.** Both use a centre square crop, a resize, and RGB 0..255 into the model (MobileNetV3 rescales internally). Augmentation runs only in the training pipeline, so the exported model has no random layers.
- **Minimalistic MobileNetV3-Small, int8.** It is small (about 600 KiB in int8) and fast on the Pi 4 CPU. The *full* variant was tried first and its hard-swish and squeeze-excite layers did not survive int8 quantization. A model at 100 % float accuracy gave inverted predictions in int8 (5.6 %), and XNNPACK refused its int8 `MEAN` ops. The minimalistic variant scored 100 % in both float and int8 on the same data, and XNNPACK accepts it. The full variant is still available with `--full-variant`, for a float-only deployment.
- **Calibration uses training pictures only.** int8 quantization calibrates on a representative set, and using test pictures would leak them into the model.
- **The review threshold is part of the evaluation.** What matters to the farmer is the accuracy of the results shown *without* "review required", and how many results that is.

## How to use it

Train on a laptop or Google Colab, not on the Pi.

```bash
python -m venv .venv-model && .venv-model/Scripts/pip install -r iot/ai/model/requirements.txt   # Linux: bin/pip
# Windows: if pip fails with a long-path error, put the venv in a short path (e.g. C:\tfv)

# 1. pictures: dataset/raw/<class>/*.jpg (iot/edge/tools/capture_dataset.py on the Pi, or an openly licensed dataset)
python iot/ai/model/prepare_dataset.py --raw dataset/raw --out dataset/split --drop-poor-quality
# 2. train (about 10 min on a laptop CPU for a few hundred pictures at 224 px)
python iot/ai/model/train.py --data dataset/split --out iot/ai/model/runs/leafscreen-0.1
# 3. export
python iot/ai/model/export_tflite.py --run iot/ai/model/runs/leafscreen-0.1 --data dataset/split --version 0.1
# 4. evaluate on the held-out pictures (writes .evaluation.json and .evaluation.md next to the model)
python iot/ai/model/evaluate.py --model iot/ai/model/export/leafscreen-0.1-int8.tflite --data dataset/split
```

Copy `leafscreen-0.1-int8.tflite` and `leafscreen-0.1-int8.json` to the Pi, set `[model] path` in `iot/edge/config.toml`, and measure the speed with `iot/edge/tools/benchmark_model.py`.

### Choosing the classes (scope §5.1, contract §10)

Start with what you can label reliably from your own plants, for example `healthy` and `stressed` (yellowing, wilting, spots). Add a class only when you have at least about 50 good pictures of it. Classes are free text: the API and the PWAs accept any label, and `unknown` means "the model cannot decide".

### Pipeline check (no real data yet)

The whole chain (prepare → train → export int8 and float → evaluate with the Pi's code → benchmark) was run on a synthetic two-class dataset (60 green-textured and 60 yellow-textured pictures, 96 px):

| Model | Size | Test accuracy | Kernels | Median latency (laptop CPU) |
|---|---|---|---|---|
| minimalistic, int8 | 602 KiB | 100 % (18/18) | XNNPACK | 0.3 ms |
| minimalistic, float | 1681 KiB | 100 % (18/18) | XNNPACK | 0.4 ms |
| full variant, int8 | 1189 KiB | 5.6 % (inverted) | built-in (XNNPACK refused) | 32.9 ms |
| full variant, float | 3649 KiB | 100 % | XNNPACK | 2.9 ms |

These numbers only show that the pipeline works. They say nothing about real basil pictures. Real accuracy and Pi latency must be measured once the dataset exists.
