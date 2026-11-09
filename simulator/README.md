# simulator

A program that behaves like the BasilCare Raspberry Pi on MQTT. It publishes sensor readings, device status, pump state and image-screening results, and it obeys pump commands with the same local safety rules as the real device. Every message follows the [MQTT contract](../docs/mqtt-contract.md).

## What it is for

- **Work without the hardware.** The team can build the Node-RED flows, the API and the PWAs before the Pi and the sensors arrive. This is the mitigation the scope gives for hardware procurement delays (risk register, §8.3).
- **Faults on demand.** Real sensors can't be made to drift when we want them to. The simulator can, so we can test incident generation (FR-03): pH drift, low water, a silent sensor, pump failure, a connection loss with late readings, and a crash.
- **A reference for `edge/`.** The real gateway must publish exactly the same messages and apply the same pump rules.

## Why it is organised this way

- **One file, [`simulator.py`](simulator.py).** The `Device` class holds all the behaviour (readings, faults, pump rules). It only builds messages and never touches the network, so [`test_simulator.py`](test_simulator.py) tests it without a broker and with a fake clock. The MQTT part (`main`) is a thin layer around it.
- **One dependency:** `paho-mqtt` 2.1.0, pinned in `requirements.txt`.
- **Simulated devices are called `basil-sim-NN`.** Their data can't be mistaken for a real Pi (`basil-pi-NN`).
- **The nominal values** (pH 6.0, EC 1.4 mS/cm, …) are realistic test data, **not** validated alert thresholds. Thresholds belong to the API's configuration (contract §3.1).

## How to use it

Requires Python 3.11+ and the Mosquitto broker from `deploy/compose.yaml`.

### 1. Install (once)

```bash
cd simulator
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash. Linux / Raspberry Pi: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the broker and watch the messages

```bash
export MSYS_NO_PATHCONV=1                                   # Git Bash only
docker compose -f deploy/compose.yaml up -d mosquitto       # from the repository root
docker exec -it basilcare-mosquitto-1 mosquitto_sub -t 'basilcare/v1/#' -v
```

(Git Bash says "the input device is not a TTY"? Put `winpty` in front of `docker exec`.)

### 3. Run the simulator (second terminal)

```bash
python simulator.py                                          # normal device, a cycle every 5 s, until Ctrl+C
python simulator.py --fault ph-drift --interval 1 --count 10
python simulator.py --device basil-sim-02 --fault low-water
```

| Option | Default | Meaning |
|---|---|---|
| `--host`, `--port` | `localhost`, `1883` | MQTT broker |
| `--device` | `basil-sim-01` | `device_id` in topics and payloads |
| `--interval` | `5` | seconds between two cycles (one reading per sensor per cycle) |
| `--count` | `0` | number of cycles; `0` = until Ctrl+C |
| `--fault` | `none` | fault to inject, see below |
| `--screening-every` | `12` | one screening result every N cycles; `0` = never |
| `--seed` | random | makes the values repeatable |

| `--fault` | What happens | Lets you test |
|---|---|---|
| `none` | readings stay near nominal values | the normal data path |
| `ph-drift` | pH rises by 0.08 per cycle | threshold incidents |
| `low-water` | water level falls by 8 points per cycle, below 20 % from cycle 8 | low-level incident; the pump stops by itself; a start is rejected |
| `stale` | the pH sensor stops at cycle 3, the others continue | per-sensor stale detection |
| `pump-failure` | the pump goes into `fault` at cycle 2 | pump-failure incident; a start is rejected |
| `outage` | cycles 3–5 are queued, then sent at cycle 6 with `buffered: true` | history vs. live display; out-of-order arrival |
| `crash` | the process dies at cycle 3 without disconnecting | the Last Will: `status` goes to `online: false` |

Ctrl+C is a clean shutdown: the simulator publishes `online: false` itself before leaving.

### 4. Send a pump command

The real path is API → `pump/cmd`. To test by hand, publish a command yourself (`expires_at` must be in the future):

```bash
docker exec basilcare-mosquitto-1 mosquitto_pub -q 1 -t basilcare/v1/basil-sim-01/pump/cmd \
  -m '{"device_id":"basil-sim-01","command_id":"test-1","action":"on","duration_s":30,"requested_by":"me","requested_at":"2026-11-04T10:00:00+01:00","expires_at":"2030-01-01T00:00:00+01:00"}'
```

The answer appears on `basilcare/v1/basil-sim-01/pump/state` (`result: executed`, or `rejected` with a `reason`). Each `command_id` is handled only once, so change it for every new command.

The simulator checks the pump timer once per cycle, so the pump can stop up to one `--interval` after `until`. The real device should use a precise timer.

### 5. Run the unit tests

```bash
python -m unittest -v
```
