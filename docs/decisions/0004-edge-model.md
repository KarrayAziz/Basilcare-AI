# ADR 0004: edge screening model is MobileNetV3-Small (minimalistic), int8 TFLite

**Status:** proposed · **Date:** 2026-11-15

## Context

Scope §5.1: a compact image classifier on the Raspberry Pi 4, with a quantized runtime if supported, a confidence indicator, image-quality checks and a "review required" fallback. The risk register lists "edge inference too slow" and "insufficient basil image data".

## Decision

- **Transfer learning** from ImageNet weights: there will only be a few hundred labelled basil pictures.
- **MobileNetV3-Small, minimalistic variant**, exported to **full-integer int8 TFLite**, run with LiteRT (`ai-edge-litert`) using XNNPACK. If XNNPACK refuses a model, the built-in kernels are used instead.
- Pre-processing is identical on the PC and the Pi: centre square crop, resize, RGB 0..255. The model rescales internally.
- `review_required` when confidence < 0.7 (configurable), when any quality check fails, or when no model is installed.

## Evidence (pipeline check on a synthetic dataset, see `iot/ai/model/README.md`)

| Variant | int8 accuracy | int8 kernels |
|---|---|---|
| full (hard-swish, squeeze-excite) | 5.6 %: predictions inverted, while float was 100 % | XNNPACK refused the int8 `MEAN` ops |
| minimalistic | 100 %, same as float | XNNPACK |

## Consequences

- About 600 KiB of model, fast enough to screen every few minutes without disturbing the measurement loop (which runs in another thread anyway).
- Real accuracy and Pi latency are still unknown until the dataset exists. `iot/ai/model/evaluate.py` and `iot/edge/tools/benchmark_model.py` produce the numbers for the design notebook.
