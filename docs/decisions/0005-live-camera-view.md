# ADR 0005: live camera view through MQTT, with an NCNN YOLO detector on the Pi

**Status:** accepted for the MVP · **Date:** 2026-11-23

## Context

For the demonstration, the only hardware available is the Raspberry Pi 4 and its camera
(v2.1). The farmer app must show the plants live, with the leaf-disease model's results drawn
on the picture. Until now, images never left the Pi (contract §6, scope §4.1): only screening
results were sent.

## Decision

- **Path:** device → MQTT `basilcare/v1/{device}/camera/live` (QoS 0) → Node-RED (contract check)
  → `POST /api/ingest/camera` (ingest key) → the API keeps the **latest frame per device in
  memory** → the farmer app polls `GET /api/camera/{device}/live` about twice a second and
  draws the boxes on a canvas. Same origin, HTTPS and login as the rest of the app; no new port.
- **Model on the Pi:** the YOLO26n detector trained in `iot/ai/model/train_yolo.py`, exported
  to **NCNN** at 320 px and run with the `ncnn` Python package (`iot/edge/basilcare_edge/detector.py`),
  without PyTorch. The same detector also feeds the 10-minute screenings (most confident
  disease, else healthy, else unknown).
- **Frames are transient:** never written on the SD card, in MongoDB or in a log; each frame
  replaces the previous one; lost frames are not retried.

## Alternatives considered

- **MJPEG served by the Pi, proxied by WildFly:** smoother (5+ frames/s), but it bypasses the
  MQTT contract and Node-RED, needs the Pi's address in the server configuration, and an
  `<img>` request cannot carry the user's bearer token.
- **ONNX Runtime or TFLite on the Pi:** ONNX Runtime is simpler to install but slower than
  NCNN on ARM; exporting YOLO to TFLite needs TensorFlow on the PC.

## Consequences

- About 1 to 4 frames per second (Pi 4, 320 px input) with up to a second of delay: enough to
  watch plants, not a video call.
- About 60 KB per frame, i.e. roughly 1 Mbit/s per device while streaming: fine on a local
  network, to be limited (lower `max_fps`, or on demand only) before many devices or a
  metered connection.
- Images now leave the device: the privacy rule of scope §4.1 has this documented exception,
  limited to in-memory frames. The broker ACL (contract §9) must allow `.../camera/live`.
- Model quality is the limit, not the pipeline: the first detector scores mAP50 0.32 on its
  held-out test set (`iot/ai/model/runs/basil-detect-0.1/test-metrics.md`), so the app
  presents boxes as hints, never as a diagnosis.
