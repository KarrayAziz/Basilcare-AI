"""Gateway configuration, read from a TOML file (see config.example.toml).

Every value has a safe default, so a minimal file only needs [device] id and [mqtt] host.
Secrets (the MQTT password) can come from the environment instead of the file:
BASILCARE_MQTT_PASSWORD overrides mqtt.password.
"""
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEVICE_ID = re.compile(r"^[a-z0-9-]{3,32}$")


@dataclass
class MqttConfig:
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    tls: bool = False
    ca_file: str = ""
    keepalive_s: int = 30


@dataclass
class PumpConfig:
    # Device-side limits (contract section 5.2). The device enforces them even when the cloud is down.
    max_duration_s: int = 900
    min_water_level: float = 20.0
    water_level_max_age_s: int = 0   # a level older than this is "unknown"; 0 = 3 x device.interval_s
    relay: str = "fake"            # "gpio" on the Pi, "fake" anywhere else
    gpio_pin: int = 17
    active_high: bool = True


@dataclass
class CameraConfig:
    enabled: bool = False
    source: str = "picamera2"      # "picamera2" on the Pi, "folder" to replay images from folder_path
    folder_path: str = ""
    width: int = 1640
    height: int = 1232
    every_s: int = 600             # one screening every 10 minutes
    images_dir: str = "data/images"
    keep_images: int = 500         # older images are deleted (storage limit of the SD card)
    controls: dict = field(default_factory=dict)   # Picamera2 controls, e.g. fixed exposure


@dataclass
class ModelConfig:
    path: str = ""                 # .tflite file; empty = no model, every screening is "review required"
    metadata: str = ""             # JSON sidecar (labels, version); default: same name with .json
    review_threshold: float = 0.7
    threads: int = 2


@dataclass
class SensorConfig:
    name: str
    driver: str = "simulated"
    options: dict = field(default_factory=dict)


@dataclass
class Config:
    device_id: str
    interval_s: int = 5
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    pump: PumpConfig = field(default_factory=PumpConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    sensors: list = field(default_factory=list)
    outbox_path: str = "data/outbox.sqlite3"
    outbox_max_rows: int = 100_000


def _section(cls, values):
    known = {f for f in cls.__dataclass_fields__}
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"unknown keys in [{cls.__name__}]: {', '.join(sorted(unknown))}")
    return cls(**values)


def load(path):
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return from_dict(raw, base_dir=Path(path).resolve().parent)


def from_dict(raw, base_dir=Path(".")):
    device = raw.get("device", {})
    device_id = device.get("id", "")
    if not DEVICE_ID.match(device_id):
        raise ValueError("device.id must be 3 to 32 characters: a-z, 0-9 and '-' (contract section 1)")
    interval = int(device.get("interval_s", 5))
    if interval < 1:
        raise ValueError("device.interval_s must be at least 1 (contract: at most one reading per second)")

    sensors = []
    for name, values in raw.get("sensors", {}).items():
        values = dict(values)
        driver = values.pop("driver", "simulated")
        sensors.append(SensorConfig(name=name, driver=driver, options=values))

    config = Config(
        device_id=device_id,
        interval_s=interval,
        mqtt=_section(MqttConfig, raw.get("mqtt", {})),
        pump=_section(PumpConfig, raw.get("pump", {})),
        camera=_section(CameraConfig, raw.get("camera", {})),
        model=_section(ModelConfig, raw.get("model", {})),
        sensors=sensors,
        outbox_path=raw.get("storage", {}).get("outbox_path", "data/outbox.sqlite3"),
        outbox_max_rows=int(raw.get("storage", {}).get("outbox_max_rows", 100_000)),
    )
    config.mqtt.password = os.environ.get("BASILCARE_MQTT_PASSWORD", config.mqtt.password)

    # relative paths are relative to the config file, so the service works from any directory
    def resolve(p):
        return str((base_dir / p).resolve()) if p and not Path(p).is_absolute() else p

    config.outbox_path = resolve(config.outbox_path)
    config.camera.images_dir = resolve(config.camera.images_dir)
    config.camera.folder_path = resolve(config.camera.folder_path)
    config.model.path = resolve(config.model.path)
    config.model.metadata = resolve(config.model.metadata)
    return config
