"""Fuse several YOLO detection datasets (e.g. Roboflow "YOLO26" exports) into one.

    python iot/ai/model/merge_yolo_datasets.py --out database/basil-merged \
        "database/Basil Disease Detection.v1i.yolo26 (1)" "database/basil downy mildew.v3i.yolo26"

What it does:
- class names are normalised (lower case, "-" and " " -> "_") and united; the first dataset's
  order is kept, new classes are appended. --rename old=new merges synonyms;
- polygon labels are converted to their bounding box, so every label is a plain box;
- finds copies of the same picture across files, splits and datasets, also when flipped or
  rotated by 90 degrees (Roboflow augmentation) or recompressed: 64-bit difference hash of the
  8 flips/rotations, grouped when within --near-duplicate bits;
- each group of copies ends up in ONE split (test > valid > train), so no picture is both
  trained on and tested on. Valid/test keep one copy of each picture (--same-picture bits);
  train keeps all copies (they act as augmentation);
- writes data.yaml, manifest.csv (every output file and where it came from), audit.json and
  SOURCES.md (licences and attribution).
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

SPLITS = ("train", "valid", "test")
PRIORITY = {"test": 0, "valid": 1, "train": 2}
TRANSFORMS = (None, Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.FLIP_TOP_BOTTOM,
              Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_270,
              Image.Transpose.TRANSPOSE, Image.Transpose.TRANSVERSE)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def long_path(path):
    """Roboflow file names can exceed Windows' 260-character path limit: use the \\\\?\\ form."""
    if os.name == "nt" and not str(path).startswith("\\\\?\\"):
        return Path("\\\\?\\" + str(path.resolve()))
    return path


def normalise(name):
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def dhash(gray):
    small = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hashes(path):
    """Difference hashes of the picture under the 8 flips/rotations; [0] is the picture as is."""
    with Image.open(path) as image:
        gray = image.convert("L").resize((64, 64), Image.Resampling.LANCZOS)
    return [dhash(gray if t is None else gray.transpose(t)) for t in TRANSFORMS]


def read_labels(path, mapping):
    """YOLO label lines -> [(class name, cx, cy, w, h)], polygons converted to boxes."""
    boxes, polygons = [], 0
    if not path.exists():
        return boxes, polygons
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        name = mapping[int(parts[0])]
        values = [float(v) for v in parts[1:]]
        if len(values) > 4:   # polygon x1 y1 x2 y2 ...
            polygons += 1
            xs, ys = values[0::2], values[1::2]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            values = [(x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0]
        boxes.append((name, *values))
    return boxes, polygons


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("datasets", nargs="+", type=Path, help="dataset folders, each with data.yaml")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--rename", action="append", default=[], metavar="OLD=NEW",
                        help="merge a class into another, after normalisation (repeatable)")
    parser.add_argument("--near-duplicate", type=int, default=4, metavar="BITS",
                        help="pictures this close share a split (same photo, or same photo session)")
    parser.add_argument("--same-picture", type=int, default=2, metavar="BITS",
                        help="valid/test keep only one of pictures this close (true copies)")
    args = parser.parse_args(argv)
    renames = dict(normalise(r).split("=", 1) for r in args.rename)

    classes, items, sources = [], [], []
    polygons = 0
    for index, root in enumerate(args.datasets):
        config = yaml.safe_load((root / "data.yaml").read_text())
        names = config["names"] if isinstance(config["names"], list) else \
            [config["names"][k] for k in sorted(config["names"])]
        mapping = {}
        for number, name in enumerate(names):
            final = renames.get(normalise(name), normalise(name))
            mapping[number] = final
            if final not in classes:
                classes.append(final)
        sources.append({"folder": root.name, "classes": names, "mapping": mapping,
                        "roboflow": config.get("roboflow", {})})
        for split in SPLITS:
            folder = long_path(root) / split / "images"
            for image in sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
                boxes, n_poly = read_labels(long_path(root) / split / "labels" / f"{image.stem}.txt", mapping)
                polygons += n_poly
                items.append({"dataset": index, "split": split, "image": image, "boxes": boxes})
        print(f"read {root.name}: {sum(1 for i in items if i['dataset'] == index)} images, classes {names}")

    print(f"hashing {len(items)} images (8 flips/rotations each)...", flush=True)
    all_hashes = [hashes(item["image"]) for item in items]
    plain = np.array([h[0] for h in all_hashes], dtype=np.uint64)
    groups = UnionFind(len(items))
    for i, variants in enumerate(all_hashes):
        close = np.zeros(len(items), dtype=bool)
        for h in variants:
            close |= np.bitwise_count(plain ^ np.uint64(h)) <= args.near_duplicate
        close[i] = False
        for j in np.flatnonzero(close):
            groups.union(i, int(j))

    members = {}
    for i in range(len(items)):
        members.setdefault(groups.find(i), []).append(i)

    audit = {"images_in": len(items), "groups": len(members), "polygons_converted": polygons,
             "dropped_cross_split_copies": 0, "dropped_extra_eval_copies": 0,
             "groups_across_splits": 0, "groups_across_datasets": 0, "label_conflicts": [],
             "per_split": {}}
    keep = []
    for group in members.values():
        splits = {items[i]["split"] for i in group}
        datasets = {items[i]["dataset"] for i in group}
        audit["groups_across_splits"] += len(splits) > 1
        audit["groups_across_datasets"] += len(datasets) > 1
        target = min(splits, key=PRIORITY.get)
        label_sets = {tuple(sorted({b[0] for b in items[i]["boxes"]})) for i in group}
        if len(label_sets) > 1:
            audit["label_conflicts"].append({
                "files": [f"{sources[items[i]['dataset']]['folder']}/{items[i]['split']}/{items[i]['image'].name}"
                          for i in group],
                "labels": sorted(label_sets)})
        in_target = [i for i in group if items[i]["split"] == target]
        audit["dropped_cross_split_copies"] += len(group) - len(in_target)
        if target != "train":   # evaluation sets: one copy per picture, distinct photos all kept
            unique = []
            for i in in_target:
                if not any(min(bin(h ^ all_hashes[k][0]).count("1") for h in all_hashes[i]) <= args.same_picture
                           for k in unique):
                    unique.append(i)
            audit["dropped_extra_eval_copies"] += len(in_target) - len(unique)
            in_target = unique
        keep.extend((i, target) for i in in_target)

    if args.out.exists():   # empty it, but keep the folder (an editor or shell may have it open)
        for child in args.out.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    rows = []
    for split in SPLITS:
        (args.out / split / "images").mkdir(parents=True)
        (args.out / split / "labels").mkdir(parents=True)
    for i, split in sorted(keep, key=lambda k: (k[1], k[0])):
        item = items[i]
        # short, stable name; the original one is kept in manifest.csv
        name = f"d{item['dataset'] + 1}_{hashlib.sha1(item['image'].name.encode()).hexdigest()[:16]}"
        shutil.copy2(item["image"], args.out / split / "images" / f"{name}{item['image'].suffix.lower()}")
        lines = [f"{classes.index(b[0])} " + " ".join(f"{v:.6f}" for v in b[1:]) for b in item["boxes"]]
        (args.out / split / "labels" / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        rows.append([f"{split}/images/{name}{item['image'].suffix.lower()}", sources[item["dataset"]]["folder"],
                     item["split"], item["image"].name, groups.find(i),
                     ";".join(sorted({b[0] for b in item["boxes"]}))])
        stats = audit["per_split"].setdefault(split, {"images": 0, "background": 0, "boxes": {}, "images_with": {}})
        stats["images"] += 1
        stats["background"] += not item["boxes"]
        for name_ in {b[0] for b in item["boxes"]}:
            stats["images_with"][name_] = stats["images_with"].get(name_, 0) + 1
        for b in item["boxes"]:
            stats["boxes"][b[0]] = stats["boxes"].get(b[0], 0) + 1

    (args.out / "data.yaml").write_text(yaml.safe_dump({
        "path": str(args.out.resolve()), "train": "train/images", "val": "valid/images",
        "test": "test/images", "nc": len(classes), "names": classes}, sort_keys=False))
    with open(args.out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "source_dataset", "source_split", "source_file", "group", "classes"])
        writer.writerows(rows)
    audit["images_out"] = len(keep)
    audit["classes"] = classes
    (args.out / "audit.json").write_text(json.dumps(audit, indent=2))
    lines = ["# Sources of this merged dataset", ""]
    for s in sources:
        rf = s["roboflow"]
        lines.append(f"- **{s['folder']}**: {rf.get('url', 'unknown source')}, licence {rf.get('license', 'unknown')}, "
                     f"workspace `{rf.get('workspace', '?')}`. Classes {s['classes']} -> "
                     f"{[s['mapping'][k] for k in sorted(s['mapping'])]}.")
    (args.out / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n{len(items)} images in, {audit['groups']} distinct pictures, {len(keep)} images out")
    print(f"copies across splits: {audit['groups_across_splits']} groups "
          f"({audit['dropped_cross_split_copies']} copies dropped); across datasets: {audit['groups_across_datasets']} groups; "
          f"extra eval copies dropped: {audit['dropped_extra_eval_copies']}; polygons converted: {polygons}")
    print(f"label conflicts (same picture, different classes): {len(audit['label_conflicts'])}")
    header = f"{'class':>16} " + " ".join(f"{s:>14}" for s in SPLITS)
    print("\nimages containing each class (boxes):\n" + header)
    for name in classes:
        cells = [f"{audit['per_split'].get(s, {}).get('images_with', {}).get(name, 0):>5} ({audit['per_split'].get(s, {}).get('boxes', {}).get(name, 0):>5})"
                 for s in SPLITS]
        print(f"{name:>16} " + " ".join(f"{c:>14}" for c in cells))
    print(f"{'background':>16} " + " ".join(f"{audit['per_split'].get(s, {}).get('background', 0):>14}" for s in SPLITS))
    print(f"{'images':>16} " + " ".join(f"{audit['per_split'].get(s, {}).get('images', 0):>14}" for s in SPLITS))


if __name__ == "__main__":
    sys.exit(main())
