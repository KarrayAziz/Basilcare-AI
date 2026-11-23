"""Leaf-screening model inference on the Raspberry Pi (scope section 5.1).

Runs a TensorFlow Lite model produced by iot/ai/model/export_tflite.py. Works with:
- an int8 full-integer model (fastest on the Pi's CPU), or
- a float32 model.
The model takes RGB pixels in 0..255 (it rescales internally) and outputs one score per class.

The interpreter comes from the first package found: ai-edge-litert (current name of the
TFLite runtime), tflite-runtime (older name), then full TensorFlow (development PC).

The labels and the model version come from the JSON sidecar written next to the model:
  {"version": "leafscreen-0.1-int8", "labels": ["healthy", "stressed"], "input_size": 224}
"""
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Prediction:
    label: str
    confidence: float
    scores: dict
    latency_ms: float


def _interpreter_classes():
    """Yields (name, class) for each installed TFLite runtime, preferred first."""
    try:
        from ai_edge_litert.interpreter import Interpreter
        yield "ai-edge-litert", Interpreter
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        yield "tflite-runtime", Interpreter
    except ImportError:
        pass
    try:
        import tensorflow as tf   # tf.lite is lazily loaded: "import tensorflow.lite" does not work
        yield "tensorflow", tf.lite.Interpreter
    except (ImportError, AttributeError):
        pass


def load_interpreter(model_path, threads=2, default_delegates=True):
    """default_delegates=False disables XNNPACK: plain built-in kernels (still optimised for int8)."""
    for name, cls in _interpreter_classes():
        options = {}
        if not default_delegates:
            if name == "tensorflow":
                import tensorflow as tf
                resolver = tf.lite.experimental.OpResolverType
            else:
                resolver = __import__(cls.__module__, fromlist=["OpResolverType"]).OpResolverType
            options["experimental_op_resolver_type"] = resolver.BUILTIN_WITHOUT_DEFAULT_DELEGATES
        return cls(model_path=str(model_path), num_threads=threads, **options)
    raise ImportError("no TFLite runtime installed: pip install ai-edge-litert (Pi) or tensorflow (PC)")


def ready_interpreter(model_path, threads=2):
    """Interpreter with tensors allocated. XNNPACK (fastest) first; some int8 graphs (e.g. the
    int8 MEAN ops of MobileNetV3's squeeze-excite blocks) are refused by XNNPACK, then the
    built-in kernels are used instead. Found with a real exported model in TF/LiteRT 2.20."""
    try:
        interpreter = load_interpreter(model_path, threads)
        interpreter.allocate_tensors()
        return interpreter, "xnnpack"
    except RuntimeError as error:
        log.warning("XNNPACK refused the model (%s); using the built-in kernels", str(error).splitlines()[0])
        interpreter = load_interpreter(model_path, threads, default_delegates=False)
        interpreter.allocate_tensors()
        return interpreter, "builtin"


def center_square(image):
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def softmax(values):
    shifted = np.exp(values - np.max(values))
    return shifted / shifted.sum()


class LeafClassifier:
    def __init__(self, model_path, metadata_path=None, threads=2, interpreter=None):
        metadata_path = Path(metadata_path) if metadata_path else Path(model_path).with_suffix(".json")
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        self.labels = list(metadata["labels"])
        self.version = metadata.get("version", Path(model_path).stem)
        if interpreter is None:
            self.interpreter, self.backend = ready_interpreter(model_path, threads)
        else:
            self.interpreter, self.backend = interpreter, "injected"
            self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]
        self.output = self.interpreter.get_output_details()[0]
        _, self.height, self.width, _ = self.input["shape"]
        classes = int(self.output["shape"][-1])
        if classes != len(self.labels):
            raise ValueError(f"model has {classes} outputs but metadata lists {len(self.labels)} labels")

    def preprocess(self, image):
        resized = center_square(image.convert("RGB")).resize((int(self.width), int(self.height)))
        pixels = np.asarray(resized, dtype=np.float32)[np.newaxis, ...]
        dtype = self.input["dtype"]
        if dtype in (np.int8, np.uint8):
            scale, zero_point = self.input["quantization"]
            info = np.iinfo(dtype)
            pixels = np.clip(np.round(pixels / scale + zero_point), info.min, info.max)
        return pixels.astype(dtype)

    def classify(self, image):
        tensor = self.preprocess(image)
        start = time.perf_counter()
        self.interpreter.set_tensor(self.input["index"], tensor)
        self.interpreter.invoke()
        raw = self.interpreter.get_tensor(self.output["index"])[0]
        latency_ms = (time.perf_counter() - start) * 1000
        scores = raw.astype(np.float32)
        scale, zero_point = self.output.get("quantization", (0.0, 0))
        if self.output["dtype"] in (np.int8, np.uint8) and scale:
            scores = (scores - zero_point) * scale
        if scores.min() < 0 or abs(float(scores.sum()) - 1.0) > 0.05:
            scores = softmax(scores)   # the model outputs logits instead of probabilities
        best = int(np.argmax(scores))
        return Prediction(self.labels[best], float(scores[best]),
                          {label: float(s) for label, s in zip(self.labels, scores)}, latency_ms)


class NoModel:
    """Used until a model is trained: every screening is 'unknown' and needs human review."""

    version = "none"
    labels = []

    def classify(self, image):
        return Prediction("unknown", 0.0, {}, 0.0)


def open_detector(config):
    """YOLO NCNN export folder -> NcnnDetector, else None."""
    if config.path and Path(config.path).is_dir():
        from .detector import NcnnDetector
        return NcnnDetector(config.path, config.threads, config.confidence, version=config.version or None)
    return None


def open_classifier(config, detector=None):
    detector = detector or open_detector(config)
    if detector is not None:
        from .detector import DetectorClassifier
        return DetectorClassifier(detector)
    if not config.path:
        return NoModel()
    return LeafClassifier(config.path, config.metadata or None, config.threads)
