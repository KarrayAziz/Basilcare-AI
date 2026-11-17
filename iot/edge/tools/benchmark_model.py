"""Measure how fast the screening model runs on this machine (scope risk "edge inference too slow").

    python tools/benchmark_model.py ../ai/model/export/leafscreen-int8.tflite --runs 50

Prints the median and 95th-percentile latency of one inference. Run it on the Pi and put the
numbers in the design notebook: they justify the screening interval and the int8 choice.
"""
import argparse
import statistics
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basilcare_edge.inference import LeafClassifier   # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model")
    parser.add_argument("--image", help="a test picture (default: a grey image)")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    classifier = LeafClassifier(args.model, threads=args.threads)
    image = Image.open(args.image).convert("RGB") if args.image else Image.new("RGB", (640, 480), (90, 140, 80))
    classifier.classify(image)   # warm-up: the first call allocates buffers
    latencies = sorted(classifier.classify(image).latency_ms for _ in range(args.runs))
    p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))]
    print(f"model {classifier.version}, input {classifier.width}x{classifier.height} "
          f"{classifier.input['dtype'].__name__}, {args.threads} thread(s), kernels: {classifier.backend}")
    print(f"latency over {args.runs} runs: median {statistics.median(latencies):.1f} ms, p95 {p95:.1f} ms")


if __name__ == "__main__":
    main()
