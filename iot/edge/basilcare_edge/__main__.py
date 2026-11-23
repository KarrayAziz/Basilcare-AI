"""Entry point:  python -m basilcare_edge --config config.toml"""
import argparse
import logging
import signal
import sys

from . import SOFTWARE, config as configuration
from .gateway import Gateway
from .outbox import Outbox
from .pump import FakeRelay, GpioRelay, PumpGuard
from .sensors import build_sensors


def build(cfg):
    context = {}
    sensors = build_sensors(cfg.sensors, context)
    relay = GpioRelay(cfg.pump.gpio_pin, cfg.pump.active_high) if cfg.pump.relay == "gpio" else FakeRelay()
    max_age = cfg.pump.water_level_max_age_s or 3 * cfg.interval_s   # same window as the cloud's stale rule
    guard = PumpGuard(cfg.device_id, relay, cfg.pump.max_duration_s, cfg.pump.min_water_level, max_age)
    outbox = Outbox(cfg.outbox_path, cfg.outbox_max_rows)
    screening = live = None
    if cfg.camera.enabled or cfg.live.enabled:
        from .camera import open_camera
        from .inference import open_classifier, open_detector
        camera = open_camera(cfg.camera)          # one camera, shared by screenings and the live view
        detector = open_detector(cfg.model)       # YOLO NCNN model, or None
        if cfg.camera.enabled:
            from .screening import ScreeningService
            screening = ScreeningService(cfg.device_id, camera, open_classifier(cfg.model, detector),
                                         cfg.camera.images_dir, cfg.camera.keep_images, cfg.model.review_threshold)
        if cfg.live.enabled:
            from .live import LiveService
            if detector is None:
                from .detector import NoDetector
                detector = NoDetector()
            live = LiveService(cfg.device_id, camera, detector, cfg.live.max_fps, cfg.live.width,
                               cfg.live.jpeg_quality)
    return Gateway(cfg, sensors, guard, outbox, screening, live=live)


def main(argv=None):
    parser = argparse.ArgumentParser(description=f"BasilCare edge gateway ({SOFTWARE})")
    parser.add_argument("--config", default="config.toml", help="TOML configuration (see config.example.toml)")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        cfg = configuration.load(args.config)
    except (OSError, ValueError) as error:
        sys.exit(f"configuration error: {error}")
    gateway = build(cfg)
    # systemd stops the service with SIGTERM: stop cleanly (pump off, status offline)
    signal.signal(signal.SIGTERM, lambda *_: gateway.stop())
    signal.signal(signal.SIGINT, lambda *_: gateway.stop())
    logging.getLogger(__name__).info("%s starting as %s, %d sensor(s), screening %s, live view %s", SOFTWARE,
                                     cfg.device_id, len(gateway.sensors), "on" if gateway.screening else "off",
                                     "on" if gateway.live else "off")
    gateway.run()


if __name__ == "__main__":
    main()
