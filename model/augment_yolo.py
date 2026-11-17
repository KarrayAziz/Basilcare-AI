"""Offline augmentation of a YOLO detection dataset (train split only).

    python model/augment_yolo.py --src database/basil-health-rev2.v2i.yolo26 --out database/basil-health-aug

Why offline, when YOLO already augments during training?
- Rare classes are OVERSAMPLED: images containing a rare class get more augmented copies,
  so the model sees many more yellow and wilting leaves per epoch.
- The transforms imitate the Raspberry Pi camera: different lighting and white balance,
  slight blur, sensor noise, JPEG compression, rotations and zoom.

Rules that keep the evaluation honest:
- only the TRAIN split is augmented; valid/ and test/ are copied unchanged;
- colour changes stay small (no hue shift), so a yellow leaf never turns green and keeps
  its label;
- a box cut by a crop is kept only if at least 40 % of it stays visible.

Output: a complete YOLO dataset (train = originals + copies, valid, test, data.yaml) and
preview.jpg with the boxes drawn on a few augmented images, to check the labels by eye.
"""
import argparse
import math
import random
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml

MIN_VISIBLE = 0.4      # keep a cropped box only if this fraction of its area is still visible
MIN_SIDE_PX = 4        # drop boxes smaller than this after the transform


# ---- labels -----------------------------------------------------------------------

def read_labels(path):
    """YOLO txt -> list of (class, x1, y1, x2, y2) in normalised corner coordinates."""
    boxes = []
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            c, x, y, w, h = int(parts[0]), *map(float, parts[1:])
            boxes.append((c, x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return boxes


def write_labels(path, boxes):
    lines = []
    for c, x1, y1, x2, y2 in boxes:
        lines.append(f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


# ---- geometric transforms (image + boxes) -------------------------------------------

def flip(image, boxes, horizontal):
    if horizontal:
        return cv2.flip(image, 1), [(c, 1 - x2, y1, 1 - x1, y2) for c, x1, y1, x2, y2 in boxes]
    return cv2.flip(image, 0), [(c, x1, 1 - y2, x2, 1 - y1) for c, x1, y1, x2, y2 in boxes]


def rotate90(image, boxes, k):
    """k quarter turns counter-clockwise."""
    for _ in range(k % 4):
        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        boxes = [(c, y1, 1 - x2, y2, 1 - x1) for c, x1, y1, x2, y2 in boxes]
    return image, boxes


def rotate_small(image, boxes, degrees):
    """Rotation by a few degrees around the centre; boxes become the enclosing box of the
    rotated corners (slightly loose, so the angle is kept small)."""
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    rotated = cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_REFLECT_101)
    out = []
    for c, x1, y1, x2, y2 in boxes:
        corners = np.array([[x1 * w, y1 * h, 1], [x2 * w, y1 * h, 1], [x1 * w, y2 * h, 1], [x2 * w, y2 * h, 1]])
        moved = corners @ matrix.T
        out.append((c, moved[:, 0].min() / w, moved[:, 1].min() / h, moved[:, 0].max() / w, moved[:, 1].max() / h))
    return rotated, clip_boxes(out, 0, 0, 1, 1)


def crop_zoom(image, boxes, rng, min_side=0.7):
    """Random crop of 70-100 % of each side, resized back to the original size (zoom in)."""
    h, w = image.shape[:2]
    side = rng.uniform(min_side, 1.0)
    cw, ch = side, side * rng.uniform(0.9, 1.1)
    ch = min(ch, 1.0)
    left, top = rng.uniform(0, 1 - cw), rng.uniform(0, 1 - ch)
    crop = image[int(top * h):int((top + ch) * h), int(left * w):int((left + cw) * w)]
    resized = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
    moved = [(c, (x1 - left) / cw, (y1 - top) / ch, (x2 - left) / cw, (y2 - top) / ch) for c, x1, y1, x2, y2 in boxes]
    return resized, clip_boxes(moved, 0, 0, 1, 1)


def clip_boxes(boxes, lo_x, lo_y, hi_x, hi_y, size=640):
    kept = []
    for c, x1, y1, x2, y2 in boxes:
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        cx1, cy1, cx2, cy2 = max(x1, lo_x), max(y1, lo_y), min(x2, hi_x), min(y2, hi_y)
        visible = max(0.0, cx2 - cx1) * max(0.0, cy2 - cy1)
        if area <= 0 or visible / area < MIN_VISIBLE:
            continue
        if (cx2 - cx1) * size < MIN_SIDE_PX or (cy2 - cy1) * size < MIN_SIDE_PX:
            continue
        kept.append((c, cx1, cy1, cx2, cy2))
    return kept


# ---- photometric transforms (image only, labels unchanged) ---------------------------

def lighting(image, rng):
    """Brightness, contrast, gamma and a small white-balance error, like a camera under
    another lamp. No hue rotation: colours keep their meaning."""
    img = image.astype(np.float32) / 255.0
    img = img * rng.uniform(0.75, 1.25) + rng.uniform(-0.06, 0.06)              # brightness
    mean = img.mean()
    img = (img - mean) * rng.uniform(0.8, 1.2) + mean                          # contrast
    img = np.clip(img, 0, 1) ** rng.uniform(0.85, 1.15)                        # gamma
    img *= np.array([rng.uniform(0.93, 1.07) for _ in range(3)], dtype=np.float32)   # white balance (BGR gains)
    hsv = cv2.cvtColor(np.clip(img, 0, 1).astype(np.float32), cv2.COLOR_BGR2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1] * rng.uniform(0.85, 1.15), 0, 1)          # saturation, small
    img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def camera_noise(image, rng):
    if rng.random() < 0.3:
        image = cv2.GaussianBlur(image, (0, 0), rng.uniform(0.4, 1.2))         # slight focus error
    if rng.random() < 0.3:
        noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(2, 8), image.shape)
        image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.4:                                                     # JPEG artefacts
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, rng.randrange(55, 95)])
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return image


def augment(image, boxes, rng):
    if rng.random() < 0.5:
        image, boxes = flip(image, boxes, horizontal=True)
    if rng.random() < 0.3:
        image, boxes = flip(image, boxes, horizontal=False)   # top-down camera: no "up" direction
    if rng.random() < 0.5:
        image, boxes = rotate90(image, boxes, rng.randrange(1, 4))
    if rng.random() < 0.4:
        image, boxes = rotate_small(image, boxes, rng.uniform(-10, 10))
    if rng.random() < 0.6:
        image, boxes = crop_zoom(image, boxes, rng)
    image = lighting(image, rng)
    image = camera_noise(image, rng)
    return image, boxes


# ---- dataset ----------------------------------------------------------------------------

def copies_for(classes_in_image, names, base, rare_extra, rare):
    extra = sum(rare_extra for name in rare if names.index(name) in classes_in_image)
    return base + extra


def preview(samples, path, names):
    colours = [(60, 60, 200), (60, 180, 60), (200, 120, 40), (40, 200, 220)]
    tiles = []
    for image, boxes in samples[:12]:
        img = image.copy()
        h, w = img.shape[:2]
        for c, x1, y1, x2, y2 in boxes:
            cv2.rectangle(img, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), colours[c % 4], 2)
            cv2.putText(img, names[c], (int(x1 * w), max(12, int(y1 * h) - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        colours[c % 4], 1, cv2.LINE_AA)
        tiles.append(cv2.resize(img, (320, 320)))
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)])
    cv2.imwrite(str(path), grid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", required=True, type=Path, help="YOLO dataset with data.yaml, train/, valid/, test/")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--copies", type=int, default=3, help="augmented copies of every training image")
    parser.add_argument("--rare", nargs="*", default=["yellow", "wilt"], help="classes to oversample")
    parser.add_argument("--rare-extra", type=int, default=4, help="extra copies per rare class present in an image")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    config = yaml.safe_load((args.src / "data.yaml").read_text())
    names = list(config["names"])
    rng = random.Random(args.seed)
    if args.out.exists():
        shutil.rmtree(args.out)

    for split in ("valid", "test"):                      # never augmented
        if (args.src / split).exists():
            shutil.copytree(args.src / split, args.out / split, ignore=shutil.ignore_patterns("*.cache"))

    out_images = args.out / "train" / "images"
    out_labels = args.out / "train" / "labels"
    out_images.mkdir(parents=True)
    out_labels.mkdir(parents=True)
    before, after = Counter(), Counter()
    samples = []
    images = sorted(p for p in (args.src / "train" / "images").iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for path in images:
        boxes = read_labels(args.src / "train" / "labels" / f"{path.stem}.txt")
        image = cv2.imread(str(path))
        shutil.copy2(path, out_images / path.name)
        write_labels(out_labels / f"{path.stem}.txt", boxes)
        for c, *_ in boxes:
            before[names[c]] += 1
            after[names[c]] += 1
        n = copies_for({b[0] for b in boxes}, names, args.copies, args.rare_extra, args.rare)
        for i in range(n):
            aug_image, aug_boxes = augment(image, boxes, rng)
            stem = f"{path.stem}_aug{i:02d}"
            cv2.imwrite(str(out_images / f"{stem}.jpg"), aug_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            write_labels(out_labels / f"{stem}.txt", aug_boxes)
            for c, *_ in aug_boxes:
                after[names[c]] += 1
            if len(samples) < 12 and rng.random() < 0.15:
                samples.append((aug_image, aug_boxes))

    config.update({"path": str(args.out.resolve()).replace("\\", "/"), "train": "train/images",
                   "val": "valid/images", "test": "test/images"})
    config["augmentation"] = {"source": str(args.src), "copies": args.copies, "rare": args.rare,
                              "rare_extra": args.rare_extra, "seed": args.seed}
    (args.out / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    if samples:
        preview(samples, args.out / "preview.jpg", names)

    n_images = len(list(out_images.iterdir()))
    print(f"train images: {len(images)} -> {n_images}")
    print(f"{'class':>10} {'boxes before':>13} {'after':>7}")
    for name in names:
        print(f"{name:>10} {before[name]:>13} {after[name]:>7}")
    print(f"valid and test copied unchanged; dataset: {args.out}")


if __name__ == "__main__":
    main()
