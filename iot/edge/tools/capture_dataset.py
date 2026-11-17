"""Collect labelled basil-leaf pictures with the Pi camera, for training the screening model.

    python tools/capture_dataset.py --label healthy --count 50 --every 3
    python tools/capture_dataset.py --label stressed --count 50 --every 3

Pictures go to dataset/raw/<label>/<label>-<timestamp>.jpg, together with their quality
measurements, so blurry or dark shots can be removed before training (iot/ai/model/prepare_dataset.py).
Move the plant or the camera a little between shots: varied angles make a better dataset.

Same camera settings as the gateway (config.toml [camera]), so training pictures look like
the pictures the model will see in production.
"""
import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basilcare_edge import config as configuration   # noqa: E402
from basilcare_edge import quality                   # noqa: E402
from basilcare_edge.camera import open_camera        # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, help="class name, e.g. healthy, stressed, yellowing")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--every", type=float, default=3.0, help="seconds between pictures")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--out", default="dataset/raw")
    args = parser.parse_args()

    cfg = configuration.load(args.config)
    camera = open_camera(cfg.camera)
    folder = Path(args.out) / args.label
    folder.mkdir(parents=True, exist_ok=True)
    log_path = folder / "quality.csv"
    new_log = not log_path.exists()
    try:
        with open(log_path, "a", newline="") as log:
            writer = csv.writer(log)
            if new_log:
                writer.writerow(["file", "issues", "brightness", "contrast", "sharpness", "green_fraction"])
            for i in range(args.count):
                image = camera.capture()
                name = f"{args.label}-{datetime.now():%Y%m%dT%H%M%S}-{i:03d}.jpg"
                image.save(folder / name, quality=92)
                issues, m = quality.assess(image)
                writer.writerow([name, " ".join(issues), *(round(m[k], 3) for k in
                                                         ("brightness", "contrast", "sharpness", "green_fraction"))])
                print(f"{i + 1}/{args.count} {name} {'OK' if not issues else 'issues: ' + ', '.join(issues)}")
                time.sleep(args.every)
    finally:
        camera.close()


if __name__ == "__main__":
    main()
