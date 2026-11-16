"""Split labelled basil pictures into train / validation / held-out test sets.

    python model/prepare_dataset.py --raw dataset/raw --out dataset/split

Input: one folder per class, e.g. dataset/raw/healthy/*.jpg, dataset/raw/stressed/*.jpg
(from edge/tools/capture_dataset.py, or an openly licensed dataset you downloaded).

What it does (scope section 5.1 "early dataset audit"):
- removes exact duplicates (same file content), so a picture cannot be in train AND test;
- optionally drops pictures that fail the edge image-quality checks (--drop-poor-quality),
  using the same code as the Pi;
- splits each class separately (stratified), 70 / 15 / 15 by default, with a fixed seed;
- writes manifest.csv (file, class, split, sha256) and audit.json (counts, warnings).
"""
import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
MIN_PER_CLASS = 30


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--drop-poor-quality", action="store_true",
                        help="drop pictures that fail edge/basilcare_edge/quality.py")
    args = parser.parse_args(argv)

    assess = None
    if args.drop_poor_quality:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "edge"))
        from PIL import Image
        from basilcare_edge.quality import assess as quality_assess

        def assess(path):
            with Image.open(path) as image:
                return quality_assess(image.convert("RGB"))[0]

    classes = sorted(p.name for p in args.raw.iterdir() if p.is_dir())
    if len(classes) < 2:
        sys.exit(f"need at least 2 class folders in {args.raw}")
    if args.out.exists():
        shutil.rmtree(args.out)

    rng = random.Random(args.seed)
    seen = {}
    rows = []
    audit = {"classes": {}, "duplicates": 0, "poor_quality": 0, "warnings": []}
    for label in classes:
        files = sorted(p for p in (args.raw / label).rglob("*") if p.suffix.lower() in SUFFIXES)
        kept = []
        for path in files:
            digest = sha256(path)
            if digest in seen:
                audit["duplicates"] += 1
                if seen[digest] != label:
                    audit["warnings"].append(f"same picture labelled {seen[digest]} and {label}: {path.name}")
                continue
            seen[digest] = label
            if assess and assess(path):
                audit["poor_quality"] += 1
                continue
            kept.append((path, digest))
        rng.shuffle(kept)
        n_test = round(len(kept) * args.test)
        n_val = round(len(kept) * args.val)
        splits = {"test": kept[:n_test], "val": kept[n_test:n_test + n_val], "train": kept[n_test + n_val:]}
        audit["classes"][label] = {name: len(items) for name, items in splits.items()}
        if len(kept) < MIN_PER_CLASS:
            audit["warnings"].append(f"class {label} has only {len(kept)} usable pictures (< {MIN_PER_CLASS})")
        for split, items in splits.items():
            folder = args.out / split / label
            folder.mkdir(parents=True, exist_ok=True)
            for path, digest in items:
                target = folder / f"{digest[:12]}{path.suffix.lower()}"
                shutil.copy2(path, target)
                rows.append([str(target.relative_to(args.out)), label, split, digest])

    with open(args.out / "manifest.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "class", "split", "sha256"])
        writer.writerows(rows)
    (args.out / "audit.json").write_text(json.dumps(audit, indent=2))
    for label, counts in audit["classes"].items():
        print(f"{label:>16}: train {counts['train']:4d}  val {counts['val']:4d}  test {counts['test']:4d}")
    print(f"duplicates removed: {audit['duplicates']}, poor quality removed: {audit['poor_quality']}")
    for warning in audit["warnings"]:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
