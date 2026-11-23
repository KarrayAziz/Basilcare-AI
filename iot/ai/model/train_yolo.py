"""Train a YOLO26 leaf-disease detector, then evaluate it ONCE on the held-out test split.

    python iot/ai/model/train_yolo.py --data database/basil-merged/data.yaml --name basil-detect-0.1

The dataset comes from merge_yolo_datasets.py (copies of a picture are never in two splits).
Validation (valid/) picks the best epoch; the test split is only used at the end, so its
numbers are an honest estimate for new pictures. Outputs, in iot/ai/model/runs/<name>/:
weights/best.pt, Ultralytics' training curves and plots, test/ (confusion matrix, PR curves)
and test-metrics.json / test-metrics.md (per-class precision, recall, mAP50, mAP50-95).
"""
import argparse
import ctypes
import json
import os
import sys
from pathlib import Path

import yaml
from dataset_audit import label_directory

HERE = Path(__file__).resolve().parent


def keep_awake(on):
    """Windows only: stop the PC from sleeping during a long training run (reset on exit)."""
    if os.name == "nt":
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def count_test_instances(data_yaml, names):
    """Boxes and images per class in the test split (to flag classes too rare to judge)."""
    config = yaml.safe_load(Path(data_yaml).read_text())
    root = Path(config.get("path") or Path(data_yaml).resolve().parent)
    if not root.is_absolute():
        root = Path(data_yaml).resolve().parent / root
    labels = label_directory(root / config["test"])
    boxes, images = [0] * len(names), [0] * len(names)
    for file in labels.rglob("*.txt"):
        seen = set()
        for line in file.read_text().splitlines():
            if line.strip():
                c = int(line.split()[0])
                boxes[c] += 1
                seen.add(c)
        for c in seen:
            images[c] += 1
    return boxes, images


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--project", type=Path, default=HERE / "runs")
    parser.add_argument("--model", default=str(HERE / "runs" / "yolo26n.pt"),
                        help="starting weights (COCO-pretrained yolo26n.pt by default)")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=20, help="stop after this many epochs without progress")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0", help="0 = first GPU, cpu = no GPU")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    from ultralytics import YOLO

    project = args.project.resolve()
    model = args.model if Path(args.model).exists() else Path(args.model).name   # else downloaded
    keep_awake(True)
    try:
        trainer_model = YOLO(model)
        trainer_model.train(data=str(args.data.resolve()), epochs=args.epochs, patience=args.patience,
                            imgsz=args.imgsz, batch=args.batch, device=args.device, workers=args.workers,
                            seed=args.seed, project=str(project), name=args.name, exist_ok=False, plots=True,
                            cache=False)
        run = Path(trainer_model.trainer.save_dir)
        best = YOLO(run / "weights" / "best.pt")
        metrics = best.val(data=str(args.data.resolve()), split="test", imgsz=args.imgsz, batch=args.batch,
                           device=args.device, project=str(run), name="test", exist_ok=True, plots=True)
    finally:
        keep_awake(False)

    names = [best.names[i] for i in range(len(best.names))]
    boxes, images = count_test_instances(args.data, names)
    per_class = {}
    for k, c in enumerate(metrics.box.ap_class_index):
        p, r, ap50, ap = metrics.box.class_result(k)
        per_class[names[int(c)]] = {"precision": float(p), "recall": float(r),
                                    "mAP50": float(ap50), "mAP50_95": float(ap),
                                    "test_images": images[int(c)], "test_boxes": boxes[int(c)]}
    overall = {"precision": float(metrics.box.mp), "recall": float(metrics.box.mr),
               "mAP50": float(metrics.box.map50), "mAP50_95": float(metrics.box.map)}
    result = {"run": run.name, "data": str(args.data), "classes": names, "overall": overall,
              "per_class": per_class, "imgsz": args.imgsz, "epochs_requested": args.epochs}
    (run / "test-metrics.json").write_text(json.dumps(result, indent=2))
    lines = [f"# {run.name}: held-out test split", "",
             "| class | test images | boxes | precision | recall | mAP50 | mAP50-95 |", "|---|---|---|---|---|---|---|"]
    for name, m in per_class.items():
        flag = " (too few to judge)" if m["test_images"] < 10 else ""
        lines.append(f"| {name}{flag} | {m['test_images']} | {m['test_boxes']} | {m['precision']:.3f} | "
                     f"{m['recall']:.3f} | {m['mAP50']:.3f} | {m['mAP50_95']:.3f} |")
    lines.append(f"| **all** | | {sum(boxes)} | {overall['precision']:.3f} | {overall['recall']:.3f} | "
                 f"{overall['mAP50']:.3f} | {overall['mAP50_95']:.3f} |")
    (run / "test-metrics.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nweights: {run / 'weights' / 'best.pt'}")


if __name__ == "__main__":   # required on Windows: data-loader workers re-import this file
    sys.exit(main())
