"""Leaf-disease detector (YOLO, exported to NCNN) for the live camera view and screenings.

Runs a model exported on the PC with

    yolo export model=runs/<name>/weights/best.pt format=ncnn imgsz=320

i.e. a folder holding model.ncnn.param, model.ncnn.bin and metadata.yaml (class names, input
size). Needs only the `ncnn`, `numpy`, `pyyaml` and `Pillow` packages: no PyTorch on the Pi.

The export (end2end: false) has one output, out0, of shape (4 + classes, candidates): box
centre x, centre y, width and height in input pixels, then one score (0..1) per class. We keep
the candidates above the confidence threshold and remove overlapping boxes of the same class
(non-maximum suppression), exactly as Ultralytics does after the network.
"""
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .inference import Prediction

log = logging.getLogger(__name__)
PAD = 114   # grey used by Ultralytics to pad the picture to a square


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple   # x1, y1, x2, y2 as fractions (0..1) of the picture's width and height


def nms(boxes, scores, iou_threshold):
    """Indices of the boxes kept, best first. boxes: (n, 4) x1 y1 x2 y2."""
    order = np.argsort(-scores)
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    keep = []
    while order.size:
        best = order[0]
        keep.append(int(best))
        rest = order[1:]
        x1 = np.maximum(boxes[best, 0], boxes[rest, 0])
        y1 = np.maximum(boxes[best, 1], boxes[rest, 1])
        x2 = np.minimum(boxes[best, 2], boxes[rest, 2])
        y2 = np.minimum(boxes[best, 3], boxes[rest, 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        iou = inter / (areas[best] + areas[rest] - inter + 1e-9)
        order = rest[iou <= iou_threshold]
    return keep


def decode(output, scale, pad_x, pad_y, width, height, labels, confidence=0.35, iou=0.5, max_detections=50):
    """Raw out0 (4 + classes, candidates) -> [Detection], boxes relative to the original picture."""
    output = np.asarray(output, dtype=np.float32)
    scores = output[4:].T
    classes = scores.argmax(axis=1)
    best = scores[np.arange(len(classes)), classes]
    mask = best >= confidence
    if not mask.any():
        return []
    cx, cy, w, h = output[:4, mask]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    classes, best = classes[mask], best[mask]
    # NMS per class: shift each class's boxes far apart so they never overlap another class
    shifted = boxes + (classes[:, None] * 10_000.0)
    keep = nms(shifted, best, iou)[:max_detections]
    detections = []
    for i in keep:
        x1, y1, x2, y2 = boxes[i]
        x1, x2 = ((np.array([x1, x2]) - pad_x) / scale / width).clip(0, 1)
        y1, y2 = ((np.array([y1, y2]) - pad_y) / scale / height).clip(0, 1)
        detections.append(Detection(labels[int(classes[i])], float(best[i]),
                                    (round(float(x1), 4), round(float(y1), 4), round(float(x2), 4), round(float(y2), 4))))
    return detections


class NcnnDetector:
    def __init__(self, folder, threads=4, confidence=0.35, iou=0.5, version=None, net=None):
        folder = Path(folder)
        import yaml
        metadata = yaml.safe_load((folder / "metadata.yaml").read_text(encoding="utf-8"))
        names = metadata["names"]
        self.labels = [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names)
        size = metadata.get("imgsz", [320, 320])
        self.size = int(size[0] if isinstance(size, (list, tuple)) else size)
        self.version = version or folder.name
        self.confidence = confidence
        self.iou = iou
        if net is None:
            import ncnn   # pip install ncnn (wheels for the Pi's 64-bit OS)
            net = ncnn.Net()
            net.opt.use_vulkan_compute = False
            net.opt.num_threads = threads
            if net.load_param(str(folder / "model.ncnn.param")) or net.load_model(str(folder / "model.ncnn.bin")):
                raise ValueError(f"could not load the NCNN model in {folder}")
        self.net = net
        log.info("detector %s: %d classes %s, input %d px", self.version, len(self.labels), self.labels, self.size)

    def letterbox(self, image):
        """Resize keeping proportions, pad to a square with grey (as in training)."""
        from PIL import Image
        image = image.convert("RGB")
        scale = min(self.size / image.width, self.size / image.height)
        w, h = round(image.width * scale), round(image.height * scale)
        pad_x, pad_y = (self.size - w) / 2, (self.size - h) / 2
        canvas = Image.new("RGB", (self.size, self.size), (PAD, PAD, PAD))
        canvas.paste(image.resize((w, h), Image.Resampling.BILINEAR), (round(pad_x - 0.1), round(pad_y - 0.1)))
        tensor = np.ascontiguousarray(np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1) / 255.0)
        return tensor, scale, round(pad_x - 0.1), round(pad_y - 0.1)

    def run(self, tensor):
        import ncnn
        with self.net.create_extractor() as extractor:
            extractor.input("in0", ncnn.Mat(tensor))
            _, out = extractor.extract("out0")
            return np.array(out)

    def detect(self, image):
        """-> ([Detection] best first, inference milliseconds)."""
        tensor, scale, pad_x, pad_y = self.letterbox(image)
        start = time.perf_counter()
        output = self.run(tensor)
        latency_ms = (time.perf_counter() - start) * 1000
        return decode(output, scale, pad_x, pad_y, image.width, image.height, self.labels,
                      self.confidence, self.iou), latency_ms


class NoDetector:
    """Live view without a model yet: the frames are shown with no boxes."""

    version = "none"
    labels = []

    def detect(self, image):
        return [], 0.0


def summarise(detections, labels):
    """One label for a whole picture, for the screening message (contract section 6): the most
    confident disease if any, else 'healthy' if a healthy leaf was found, else 'unknown'."""
    diseases = [d for d in detections if d.label != "healthy"]
    if diseases:
        best = max(diseases, key=lambda d: d.confidence)
    elif detections:
        best = max(detections, key=lambda d: d.confidence)
    else:
        return Prediction("unknown", 0.0, {}, 0.0)
    scores = {label: max((d.confidence for d in detections if d.label == label), default=0.0) for label in labels}
    return Prediction(best.label, best.confidence, scores, 0.0)


class DetectorClassifier:
    """Lets the 10-minute screening (screening.py) use the detector: one label per picture."""

    def __init__(self, detector):
        self.detector = detector
        self.version = detector.version
        self.labels = detector.labels

    def classify(self, image):
        detections, latency_ms = self.detector.detect(image)
        prediction = summarise(detections, self.labels)
        prediction.latency_ms = latency_ms
        return prediction
