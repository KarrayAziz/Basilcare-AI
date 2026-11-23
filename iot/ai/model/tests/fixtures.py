"""Tiny artificial images and fabricated metrics for software tests, not model evaluation."""
import json
from pathlib import Path

from PIL import Image
import yaml

NAMES = ["healthy", "stressed"]
POLICY = {"version": "software-test-fixture", "minimum_overall": {"mAP50": 0.5},
          "minimum_per_class": {"recall": 0.5}, "minimum_test_images_per_class": 1}


def dataset(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for s, split in enumerate(("train", "valid", "test")):
        images = root / split / "images"
        labels = root / split / "labels"
        images.mkdir(parents=True)
        labels.mkdir()
        for c in range(2):
            Image.new("RGB", (12, 12), (20 + 50 * s, 30 + 60 * c, 100)).save(images / f"{c}.png")
            (labels / f"{c}.txt").write_text(f"{c} 0.5 0.5 0.4 0.4\n")
    path = root / "data.yaml"
    path.write_text(yaml.safe_dump({"path": ".", "train": "train/images", "val": "valid/images",
                                    "test": "test/images", "names": NAMES}))
    return path


def metrics(audit):
    values = {"precision": 0.8, "recall": 0.7, "mAP50": 0.7, "mAP50_95": 0.4}
    return {"classes": NAMES, "overall": values.copy(), "per_class": {
        name: {**values, "test_images": audit["splits"]["test"]["images_with"][name],
               "test_boxes": audit["splits"]["test"]["boxes"][name]} for name in NAMES}}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(dataset(args.out))
