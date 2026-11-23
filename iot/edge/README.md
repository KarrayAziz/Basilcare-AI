# edge

The program that runs on the **Raspberry Pi 4** (scope §3.1, §4, §5.1). It reads the sensors, keeps readings in a local queue while the network is down, publishes everything over MQTT exactly as [`docs/mqtt-contract.md`](../../docs/mqtt-contract.md) says, enforces pump safety locally, and screens leaf pictures with an on-device model.

```
sensors (simulated or real) ─► measure every interval_s ─► SQLite outbox ─► MQTT (QoS 1) ─► Mosquitto
camera ─► quality checks ─► TFLite model ─► screening result ─┘          ▲ deleted only on PUBACK
pump/cmd ─► PumpGuard (contract §5.2 rules) ─► relay ─► pump/state (retained)
           watchdog every 0.5 s: stops the pump when its time is up or the water is low
```

It works **today with only the Pi and its camera**: every sensor can be `simulated` until the probes arrive, and switching one to the real probe is a one-line change in `config.toml`.

## What it does

| Module | Role |
|---|---|
| [`gateway.py`](basilcare_edge/gateway.py) | main loop: measurement cycle, queue sending, pump watchdog, screening thread; MQTT connection with Last Will |
| [`outbox.py`](basilcare_edge/outbox.py) | SQLite queue: a message is deleted only when the broker acknowledged it, so an outage or a power cut loses nothing; bounded (oldest dropped first) |
| [`pump.py`](basilcare_edge/pump.py) | local safety rules of contract §5.2; relay off at start and stop; automatic stop after `duration_s` or on low water, **even without network** |
| [`sensors/`](basilcare_edge/sensors) | `simulated` driver, and drivers for BME280, DS18B20 and ADS1115 (pH, EC, level) with calibration |
| [`camera.py`](basilcare_edge/camera.py) | Pi camera (Picamera2) or a folder of pictures (development) |
| [`quality.py`](basilcare_edge/quality.py) | too dark / too bright / low contrast / blurry / no leaf in frame |
| [`inference.py`](basilcare_edge/inference.py) | TFLite model (int8 or float), labels and version from the JSON sidecar written by `iot/ai/model/` |
| [`screening.py`](basilcare_edge/screening.py) | capture → quality → model → keep the image on the Pi → `screening` message, `review_required` when unsure |
| [`detector.py`](basilcare_edge/detector.py) | YOLO leaf-disease detector exported to NCNN (`ncnn` package, no PyTorch): letterbox, boxes, per-class NMS; also gives one label per picture to the screenings |
| [`live.py`](basilcare_edge/live.py) | live camera view: capture → detector → 640 px JPEG + boxes → `camera/live` (QoS 0, only while connected, never stored) |

## Why it is organised this way

- **Same contract as the simulator.** A unit test checks that the gateway's messages have exactly the simulator's fields, so Node-RED and the API cannot tell them apart.
- **Queue first, then publish.** Every reading goes to SQLite before MQTT. A reading published late is flagged `buffered: true` at sending time (older than 1.5 × interval), so the cloud stores it as history and never shows it as the live value (scope §2.3).
- **Two independent safety barriers.** The API checks a pump request (`PumpSafetyPolicy`), and the Pi checks it again here. The Pi's check does not need the cloud, and neither an API bug nor the AI assistant can bypass it.
- **Hardware libraries are imported lazily**, only by the drivers that need them, so the whole gateway runs and is tested on a laptop.
- **Images stay on the Pi** (contract §6). Only the result is sent; `image_id` lets a person find the picture for review. The one exception is the optional live view (contract §6a, [ADR 0005](../../docs/decisions/0005-live-camera-view.md)): small frames kept only in memory, by the Pi and by the API.
- **A slow model never delays readings**: screening runs in its own thread.

## How to use it

### On the Raspberry Pi (Raspberry Pi OS 64-bit, Bookworm)

```bash
sudo apt install -y python3-picamera2 python3-venv git
git clone <repository> && cd Basilcare-AI/iot/edge
python3 -m venv --system-site-packages .venv     # system packages: Picamera2 comes from apt
.venv/bin/pip install -r requirements-pi.txt
cp config.example.toml config.toml               # set device.id and mqtt.host (your laptop's IP)
rpicam-still -o test.jpg                         # camera check
.venv/bin/python -m basilcare_edge --config config.toml
```

Register the device id in the admin PWA (or `POST /api/devices`) so the API accepts pump commands for it.

**Live camera view with the disease detector.** Copy the NCNN export from the PC (`iot/ai/model/runs/<run>/weights/best_ncnn_model/`) to the Pi, for example `iot/edge/models/basil-detect-0.1-ncnn320/`, then in `config.toml`:

```toml
[camera]
enabled = true                # 10-minute screenings, now from the detector
source = "picamera2"
[model]
path = "models/basil-detect-0.1-ncnn320"
[live]
enabled = true
max_fps = 2
```

The farmer app then shows a **Live camera** card with the boxes. To start at boot, install [`systemd/basilcare-edge.service`](systemd/basilcare-edge.service) (instructions inside the file).

### On a laptop (no Pi needed)

```bash
cd iot/edge
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
cp config.example.toml config.toml   # mqtt.host = "localhost"; camera.source = "folder"; camera.folder_path = some pictures
.venv/Scripts/python -m basilcare_edge --config config.toml
```

### When a probe arrives

Replace its `[sensors.*]` section in `config.toml` (examples in [`config.example.toml`](config.example.toml)), calibrate it (pH: voltages in the pH 7 and pH 4 buffers; EC: reference solution; level: empty and full), and restart. Readings switch to `calibrated: true` automatically once the calibration values are set. The drivers in [`sensors/hardware.py`](basilcare_edge/sensors/hardware.py) are written from the libraries' documentation and **not yet tested on hardware**.

### Collecting the dataset and testing the model

```bash
.venv/bin/python tools/capture_dataset.py --label healthy --count 50      # pictures + quality log
.venv/bin/python tools/benchmark_model.py ../ai/model/export/leafscreen-int8.tflite --runs 50
```

Then train and export the model with [`iot/ai/model/`](../ai/model/README.md) and set `[model] path` in `config.toml`.

### Tests

```bash
cd iot/edge && .venv/Scripts/python -m unittest discover -s tests -t .
```

37 tests: contract shapes (cross-checked with the simulator), outbox (acknowledgement, outage, power cut, bound), every pump rule and the watchdog, sensor conversions, image quality, int8/float inference with a fake interpreter, the screening chain, and the gateway with a fake MQTT client (buffered flag, resend after disconnection, broken probe, clean shutdown).

Tested live against the Docker stack: the broker stopped for 25 s, then 34/34 readings stored with no `seq` gap and 13 correctly flagged `buffered`. This needs the broker's persistence, which is enabled in [`deploy/mosquitto/mosquitto.conf`](../../deploy/mosquitto/mosquitto.conf).
