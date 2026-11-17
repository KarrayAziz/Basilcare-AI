import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from basilcare_edge import quality
from basilcare_edge.camera import FolderCamera
from basilcare_edge.inference import LeafClassifier, NoModel
from basilcare_edge.screening import ScreeningService
from tests.helpers import Clock, leaf_image


class QualityTest(unittest.TestCase):
    def test_a_good_leaf_picture_passes(self):
        issues, _ = quality.assess(leaf_image())
        self.assertEqual([], issues)

    def test_dark_bright_blurry_and_empty_pictures(self):
        self.assertIn("too_dark", quality.assess(Image.new("RGB", (640, 480), (10, 20, 10)))[0])
        self.assertIn("too_bright", quality.assess(Image.new("RGB", (640, 480), (250, 250, 250)))[0])
        self.assertIn("blurry", quality.assess(leaf_image().filter(ImageFilter.GaussianBlur(8)))[0])
        grey = Image.fromarray(np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8))
        self.assertIn("out_of_frame", quality.assess(grey.convert("L").convert("RGB"))[0])


class FakeInterpreter:
    """Mimics the TFLite interpreter API with fixed outputs."""

    def __init__(self, outputs, input_dtype=np.float32, output_dtype=np.float32, out_quant=(0.0, 0)):
        self.outputs = np.array([outputs], dtype=output_dtype)
        self.input_dtype = input_dtype
        self.output_dtype = output_dtype
        self.out_quant = out_quant
        self.received = None

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{"index": 0, "shape": np.array([1, 96, 96, 3]), "dtype": self.input_dtype,
                 "quantization": (1.0, -128) if self.input_dtype == np.int8 else (0.0, 0)}]

    def get_output_details(self):
        return [{"index": 1, "shape": np.array([1, self.outputs.shape[1]]), "dtype": self.output_dtype,
                 "quantization": self.out_quant}]

    def set_tensor(self, index, tensor):
        self.received = tensor

    def invoke(self):
        pass

    def get_tensor(self, index):
        return self.outputs


class InferenceTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.meta = Path(self.folder.name) / "model.json"
        self.meta.write_text(json.dumps({"version": "leafscreen-test", "labels": ["healthy", "stressed"]}))

    def tearDown(self):
        self.folder.cleanup()

    def classifier(self, interpreter):
        return LeafClassifier(Path(self.folder.name) / "model.tflite", self.meta, interpreter=interpreter)

    def test_float_model_probabilities(self):
        result = self.classifier(FakeInterpreter([0.2, 0.8])).classify(leaf_image())
        self.assertEqual(("stressed", 0.8), (result.label, round(result.confidence, 3)))

    def test_logits_are_turned_into_probabilities(self):
        result = self.classifier(FakeInterpreter([2.0, -1.0])).classify(leaf_image())
        self.assertEqual("healthy", result.label)
        self.assertAlmostEqual(1.0, sum(result.scores.values()), places=5)

    def test_int8_model_input_is_quantized_and_output_dequantized(self):
        interpreter = FakeInterpreter([-128 + 230, -128 + 25], np.int8, np.int8, out_quant=(1 / 255, -128))
        result = self.classifier(interpreter).classify(leaf_image())
        self.assertEqual(np.int8, interpreter.received.dtype)
        self.assertEqual((1, 96, 96, 3), interpreter.received.shape)
        self.assertEqual("healthy", result.label)
        self.assertAlmostEqual(230 / 255, result.confidence, places=3)

    def test_labels_must_match_the_model(self):
        with self.assertRaises(ValueError):
            self.classifier(FakeInterpreter([0.1, 0.2, 0.7]))


class ScreeningServiceTest(unittest.TestCase):
    def test_full_chain_with_review_rules_and_image_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pictures"
            source.mkdir()
            leaf_image().save(source / "a.jpg", quality=95)
            Image.new("RGB", (640, 480), (5, 5, 5)).save(source / "b.jpg")
            clock = Clock()
            service = ScreeningService("basil-pi-01", FolderCamera(source), NoModel(), Path(folder) / "kept",
                                       keep_images=1, clock=clock)

            topic, good, _ = service.run()
            self.assertEqual("basilcare/v1/basil-pi-01/screening", topic)
            self.assertEqual("basil-pi-01-20261104T140000", good["image_id"])
            self.assertTrue(good["quality_ok"])
            self.assertTrue(good["review_required"], "no model yet: always needs review")
            self.assertEqual("none", good["model_version"])

            clock.advance(600)
            _, dark, _ = service.run()
            self.assertIn("too_dark", dark["quality_issues"])
            self.assertEqual(1, len(list((Path(folder) / "kept").glob("*.jpg"))), "only the newest image is kept")


if __name__ == "__main__":
    unittest.main()
