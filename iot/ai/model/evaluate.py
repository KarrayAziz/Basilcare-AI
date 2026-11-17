"""Evaluate an exported model on the held-out test pictures (scope section 5.4).

    python iot/ai/model/evaluate.py --model iot/ai/model/export/leafscreen-0.1-int8.tflite --data dataset/split

Uses the SAME inference code as the Raspberry Pi (iot/edge/basilcare_edge/inference.py), so the
numbers describe what the Pi will actually do, quantization included.

Reports (printed, and written next to the model as <name>.evaluation.json / .md):
- confusion matrix, per-class precision / recall / F1, accuracy;
- the effect of the review threshold: how many results would be shown without
  "review required", and how accurate those are. This is the number that matters for the
  farmer: a low-confidence result is never presented as reliable.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "edge"))

from basilcare_edge.inference import LeafClassifier   # noqa: E402

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def metrics(labels, truth, predicted):
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(truth, predicted):
        matrix[index[t]][index[p]] += 1
    per_class = {}
    for i, label in enumerate(labels):
        tp = matrix[i][i]
        fp = sum(matrix[r][i] for r in range(len(labels))) - tp
        fn = sum(matrix[i]) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[i])}
    accuracy = sum(matrix[i][i] for i in range(len(labels))) / max(1, len(truth))
    return matrix, per_class, accuracy


def markdown(name, labels, matrix, per_class, accuracy, threshold, coverage, covered_accuracy, latency):
    lines = [f"# Evaluation of {name}", "",
             f"Held-out test set, {sum(map(sum, matrix))} pictures. Accuracy **{accuracy:.1%}**. "
             f"Median latency on this machine {latency:.1f} ms.", "",
             "## Confusion matrix (rows: truth, columns: prediction)", "",
             "| truth \\ predicted | " + " | ".join(labels) + " |",
             "|---|" + "---|" * len(labels)]
    lines += [f"| {label} | " + " | ".join(str(v) for v in row) + " |" for label, row in zip(labels, matrix)]
    lines += ["", "## Per class", "", "| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |"
              for k, v in per_class.items()]
    lines += ["", f"## Review threshold {threshold}", "",
              f"{coverage:.1%} of the results reach the threshold and are shown without \"review required\"; "
              f"their accuracy is {covered_accuracy:.1%}. The others are always flagged for a person to check."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.7, help="review_threshold of the Pi")
    args = parser.parse_args(argv)

    classifier = LeafClassifier(args.model)
    truth, predicted, confidences, latencies = [], [], [], []
    for label_dir in sorted((args.data / "test").iterdir()):
        if not label_dir.is_dir():
            continue
        for path in sorted(p for p in label_dir.iterdir() if p.suffix.lower() in SUFFIXES):
            with Image.open(path) as image:
                result = classifier.classify(image.convert("RGB"))
            truth.append(label_dir.name)
            predicted.append(result.label)
            confidences.append(result.confidence)
            latencies.append(result.latency_ms)
    unknown = set(truth) - set(classifier.labels)
    if unknown:
        sys.exit(f"test classes not known by the model: {unknown}")

    matrix, per_class, accuracy = metrics(classifier.labels, truth, predicted)
    covered = [(t, p) for t, p, c in zip(truth, predicted, confidences) if c >= args.threshold]
    coverage = len(covered) / max(1, len(truth))
    covered_accuracy = sum(t == p for t, p in covered) / max(1, len(covered))
    latency = sorted(latencies)[len(latencies) // 2] if latencies else 0.0

    report = {"model": classifier.version, "pictures": len(truth), "accuracy": accuracy, "labels": classifier.labels,
              "confusion_matrix": matrix, "per_class": per_class, "review_threshold": args.threshold,
              "coverage_above_threshold": coverage, "accuracy_above_threshold": covered_accuracy,
              "median_latency_ms": latency}
    base = args.model.with_suffix("")
    Path(f"{base}.evaluation.json").write_text(json.dumps(report, indent=2))
    text = markdown(classifier.version, classifier.labels, matrix, per_class, accuracy, args.threshold, coverage,
                    covered_accuracy, latency)
    Path(f"{base}.evaluation.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
