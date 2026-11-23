"""Split labelled basil pictures into train / validation / held-out test sets.

    python iot/ai/model/prepare_dataset.py --raw dataset/raw --out dataset/split

Input: one folder per class, e.g. dataset/raw/healthy/*.jpg, dataset/raw/stressed/*.jpg
(from iot/edge/tools/capture_dataset.py, or an openly licensed dataset you downloaded).

What it does (scope section 5.1 "early dataset audit"):
- removes exact duplicates (same file content) and near-duplicates (same picture resized or
  recompressed, 64-bit difference hash within --near-duplicate bits), so a picture cannot be
  in train AND test; a near-duplicate under two different classes is reported as a conflict;
- converts formats YOLO and the Pi cannot all read (.webp, .jfif, .png with alpha...) to JPEG;
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

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jfif"}
KEEP_AS_IS = {".jpg", ".jpeg"}
MIN_PER_CLASS = 30


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dhash(image):
    """64-bit difference hash: survives resizing and recompression, not cropping."""
    from PIL import Image
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--near-duplicate", type=int, default=4, metavar="BITS",
                        help="max differing hash bits to treat two pictures as the same (0 = exact only)")
    parser.add_argument("--drop-poor-quality", action="store_true",
                        help="drop pictures that fail iot/edge/basilcare_edge/quality.py")
    args = parser.parse_args(argv)

    assess = None
    if args.drop_poor_quality:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "edge"))
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
    from PIL import Image, ImageOps

    seen = {}
    hashes = []          # (dhash, label, file name) of every kept picture
    rows = []
    audit = {"classes": {}, "duplicates": 0, "near_duplicates": 0, "unreadable": 0,
             "converted": 0, "poor_quality": 0, "warnings": []}
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
            try:
                with Image.open(path) as image:
                    fingerprint = dhash(ImageOps.exif_transpose(image))
            except Exception as error:   # truncated or not really an image
                audit["unreadable"] += 1
                audit["warnings"].append(f"unreadable picture {label}/{path.name}: {error}")
                continue
            twin = next((h for h in hashes if bin(h[0] ^ fingerprint).count("1") <= args.near_duplicate), None)
            if twin:
                audit["near_duplicates"] += 1
                if twin[1] != label:
                    audit["warnings"].append(
                        f"near-identical pictures labelled {twin[1]} ({twin[2]}) and {label} ({path.name})")
                continue
            hashes.append((fingerprint, label, path.name))
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
                if path.suffix.lower() in KEEP_AS_IS:
                    target = folder / f"{digest[:12]}{path.suffix.lower()}"
                    shutil.copy2(path, target)
                else:
                    target = folder / f"{digest[:12]}.jpg"
                    with Image.open(path) as image:
                        ImageOps.exif_transpose(image).convert("RGB").save(target, "JPEG", quality=95)
                    audit["converted"] += 1
                rows.append([str(target.relative_to(args.out)), label, split, digest])

    with open(args.out / "manifest.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "class", "split", "sha256"])
        writer.writerows(rows)
    (args.out / "audit.json").write_text(json.dumps(audit, indent=2))
    for label, counts in audit["classes"].items():
        print(f"{label:>16}: train {counts['train']:4d}  val {counts['val']:4d}  test {counts['test']:4d}")
    print(f"duplicates removed: {audit['duplicates']} exact, {audit['near_duplicates']} near; "
          f"unreadable: {audit['unreadable']}; poor quality removed: {audit['poor_quality']}; "
          f"converted to JPEG: {audit['converted']}")
    for warning in audit["warnings"]:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
