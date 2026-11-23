"""Audit the final directory-based YOLO box dataset before training (no ML runtime needed)."""
import hashlib
import json
import math
from pathlib import Path

import yaml
from PIL import Image

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def label_directory(images):
    parts = list(Path(images).parts)
    positions = [i for i, part in enumerate(parts) if part == "images"]
    if not positions:
        raise ValueError("image directory must contain an 'images' path component to locate labels")
    parts[positions[-1]] = "labels"
    return Path(*parts)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_config(data):
    data = Path(data).resolve()
    config = yaml.safe_load(data.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("data.yaml must contain a mapping")
    names = config.get("names")
    if isinstance(names, dict):
        if set(names) != set(range(len(names))) or any(type(k) is not int for k in names):
            raise ValueError("class IDs must be consecutive integers starting at zero")
        names = [names[i] for i in range(len(names))]
    if (not isinstance(names, list) or not names
            or any(not isinstance(n, str) or not n.strip() for n in names)
            or len(set(names)) != len(names)):
        raise ValueError("names must be nonempty, unique class names")
    if config.get("nc", len(names)) != len(names):
        raise ValueError("nc does not match names")
    root = Path(config.get("path") or data.parent)
    if not root.is_absolute():
        root = data.parent / root
    splits = {}
    for split in ("train", "val", "test"):
        value = config.get(split)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{split}: an image directory is required (not a file list)")
        folder = (root / value).resolve()
        if not folder.is_dir():
            raise ValueError(f"{split}: expected an existing image directory: {folder}")
        label_directory(folder)
        splits[split] = folder
    if len(set(splits.values())) != 3:
        raise ValueError("train, val and test must use distinct image directories")
    return names, splits


def audit_dataset(data):
    """Return content fingerprint, support counts and actionable errors. Never modifies data."""
    names, folders = read_config(data)
    records, errors, seen = [], [], {}
    counts = {s: {"images": 0, "boxes": dict.fromkeys(names, 0),
                  "images_with": dict.fromkeys(names, 0)} for s in folders}
    for split, folder in folders.items():
        labels = label_directory(folder)
        entries = sorted(folder.rglob("*"))
        for entry in entries:
            if entry.is_symlink() or (entry.is_file() and entry.suffix.lower() not in SUFFIXES):
                errors.append(f"{split}: unsupported image-directory entry: {entry.relative_to(folder)}")
        images = [p for p in entries if p.is_file() and p.suffix.lower() in SUFFIXES]
        if not images:
            errors.append(f"{split}: no images")
        expected_labels = set()
        for image in images:
            relative = image.relative_to(folder)
            label = labels / relative.with_suffix(".txt")
            expected_labels.add(label.resolve())
            name = f"{split}/{relative.as_posix()}"
            counts[split]["images"] += 1
            row = {"image": name, "image_sha256": sha256(image), "label_sha256": None}
            try:
                with Image.open(image) as picture:
                    picture = picture.convert("RGB")
                    pixels = hashlib.sha256(str(picture.size).encode() + b":" + picture.tobytes()).hexdigest()
                row["pixels_sha256"] = pixels
                previous = seen.setdefault(pixels, (split, name))
                if previous[0] != split:
                    errors.append(f"cross-split duplicate: {previous[1]} and {name}")
            except (OSError, ValueError, Image.DecompressionBombError) as error:
                errors.append(f"{name}: unreadable image ({error})")
            present = set()
            if not label.is_file():
                errors.append(f"{name}: missing label file (use an empty file for a background image)")
            else:
                row["label_sha256"] = sha256(label)
                for number, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        parts = line.split()
                        if len(parts) != 5:
                            raise ValueError("expected class cx cy width height; convert polygons first")
                        class_id = int(parts[0])
                        box = [float(v) for v in parts[1:]]
                        if not 0 <= class_id < len(names):
                            raise ValueError("class ID outside names")
                        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in box) or min(box[2:]) <= 0:
                            raise ValueError("box coordinates must be finite and normalized; size must be positive")
                        class_name = names[class_id]
                        counts[split]["boxes"][class_name] += 1
                        present.add(class_name)
                    except ValueError as error:
                        errors.append(f"{name}, label line {number}: {error}")
            for class_name in present:
                counts[split]["images_with"][class_name] += 1
            records.append(row)
        if labels.is_dir():
            for orphan in sorted(labels.rglob("*.txt")):
                if orphan.resolve() not in expected_labels:
                    errors.append(f"{split}: label without image: {orphan.relative_to(labels)}")
    fingerprint = hashlib.sha256(json.dumps({"classes": names, "files": records},
                                            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"ok": not errors, "fingerprint": fingerprint, "classes": names, "splits": counts,
            "errors": errors, "files": records,
            "duplicate_check": "identical decoded RGB pixels across splits; not a near-duplicate detector"}


def resolved_config(data):
    """Avoid Ultralytics' global datasets-directory resolution of relative paths."""
    names, folders = read_config(data)
    return {"names": names, "nc": len(names), **{s: str(p) for s, p in folders.items()}}
