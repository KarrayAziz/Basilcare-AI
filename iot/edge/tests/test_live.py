import base64
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from basilcare_edge import config as configuration
from basilcare_edge.camera import FolderCamera
from basilcare_edge.detector import Detection, DetectorClassifier, NcnnDetector, NoDetector, decode, nms, summarise
from basilcare_edge.live import LiveService
from tests.helpers import Clock, leaf_image

LABELS = ["leaf_spot", "downy_mildew", "fusarium_wilt", "healthy", "powdery_mildew"]


def raw_output(candidates):
    """Builds an out0 array (4 + classes, n) from [(cx, cy, w, h, class index, score)]."""
    out = np.zeros((4 + len(LABELS), len(candidates)), dtype=np.float32)
    for i, (cx, cy, w, h, c, s) in enumerate(candidates):
        out[:4, i] = (cx, cy, w, h)
        out[4 + c, i] = s
    return out


class FakeNet:
    """Stands in for ncnn.Net: returns a fixed out0, whatever the input."""

    def __init__(self, output):
        self.output = output


class FakeDetector(NcnnDetector):
    def __init__(self, output, folder):
        super().__init__(folder, net=FakeNet(output), version="fake-0.1")

    def run(self, tensor):
        assert tensor.shape == (3, self.size, self.size) and tensor.max() <= 1.0
        return self.net.output


def model_folder():
    folder = Path(tempfile.mkdtemp())
    (folder / "metadata.yaml").write_text("imgsz:\n- 320\n- 320\nnames:\n" +
                                          "".join(f"  {i}: {n}\n" for i, n in enumerate(LABELS)))
    return folder


class DecodeTest(unittest.TestCase):
    def test_overlapping_boxes_of_one_class_are_merged_other_classes_kept(self):
        out = raw_output([(100, 100, 50, 50, 1, 0.9), (102, 101, 50, 50, 1, 0.6),   # same leaf twice
                          (100, 100, 50, 50, 3, 0.5),                                 # other class, same place
                          (250, 250, 40, 40, 2, 0.2)])                                # below the threshold
        found = decode(out, scale=1.0, pad_x=0, pad_y=0, width=320, height=320, labels=LABELS)
        self.assertEqual([("downy_mildew", 0.9), ("healthy", 0.5)],
                         [(d.label, round(d.confidence, 2)) for d in found])
        self.assertEqual((75 / 320, 75 / 320, 125 / 320, 125 / 320), tuple(round(v * 320) / 320 for v in found[0].box))

    def test_letterbox_padding_and_scale_are_undone(self):
        # a 640x320 picture is scaled by 0.5 to 320x160 and padded by 80 px at the top
        out = raw_output([(160, 160, 320, 160, 0, 0.8)])   # the whole picture area
        box = decode(out, scale=0.5, pad_x=0, pad_y=80, width=640, height=320, labels=LABELS)[0].box
        self.assertEqual((0.0, 0.0, 1.0, 1.0), box)

    def test_nms_keeps_best_first(self):
        boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
        self.assertEqual([2, 0], nms(boxes, np.array([0.5, 0.4, 0.9]), 0.5))


class SummaryTest(unittest.TestCase):
    def test_a_disease_wins_over_healthy_leaves(self):
        found = [Detection("healthy", 0.9, (0, 0, 1, 1)), Detection("downy_mildew", 0.5, (0, 0, 1, 1))]
        self.assertEqual(("downy_mildew", 0.5), (summarise(found, LABELS).label, summarise(found, LABELS).confidence))

    def test_only_healthy_and_nothing_found(self):
        self.assertEqual("healthy", summarise([Detection("healthy", 0.7, (0, 0, 1, 1))], LABELS).label)
        self.assertEqual("unknown", summarise([], LABELS).label)

    def test_screening_adapter_uses_the_detector(self):
        detector = FakeDetector(raw_output([(160, 160, 100, 100, 4, 0.8)]), model_folder())
        prediction = DetectorClassifier(detector).classify(leaf_image())
        self.assertEqual(("powdery_mildew", 0.8), (prediction.label, round(prediction.confidence, 2)))
        self.assertEqual(LABELS, detector.labels)
        self.assertEqual(320, detector.size)


class LiveServiceTest(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp())
        leaf_image().resize((1280, 960)).save(folder / "leaf.jpg")
        self.camera = FolderCamera(folder)

    def test_frame_message_is_small_and_complete(self):
        detector = FakeDetector(raw_output([(160, 160, 100, 100, 1, 0.7)]), model_folder())
        live = LiveService("basil-pi-01", self.camera, detector, max_fps=2, width=640, clock=Clock())
        topic, payload, retain = live.frame()
        self.assertEqual("basilcare/v1/basil-pi-01/camera/live", topic)
        self.assertFalse(retain)
        self.assertEqual((640, 480), (payload["width"], payload["height"]))
        image = Image.open(io.BytesIO(base64.b64decode(payload["image_jpeg"])))
        self.assertEqual((640, 480), image.size)
        self.assertLess(len(json.dumps(payload)), 200_000)
        self.assertEqual("downy_mildew", payload["detections"][0]["label"])
        self.assertEqual(4, len(payload["detections"][0]["box"]))
        self.assertEqual(("fake-0.1", 1), (payload["model_version"], payload["frame_id"]))

    def test_publishes_only_while_connected_and_stops(self):
        sent, connected, stop = [], threading.Event(), threading.Event()
        live = LiveService("basil-pi-01", self.camera, NoDetector(), max_fps=10, clock=Clock())
        thread = threading.Thread(target=live.run, args=(lambda t, p: sent.append(p), connected, stop))
        thread.start()
        stop.wait(0.3)
        self.assertEqual([], sent)                 # not connected: nothing published
        connected.set()
        stop.wait(0.5)
        stop.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(len(sent), 2)
        self.assertEqual([], sent[0]["detections"])


class LiveConfigTest(unittest.TestCase):
    def test_live_section_and_limits(self):
        cfg = configuration.from_dict({"device": {"id": "basil-pi-01"}, "live": {"enabled": True, "max_fps": 3}})
        self.assertTrue(cfg.live.enabled)
        self.assertEqual(3, cfg.live.max_fps)
        with self.assertRaises(ValueError):
            configuration.from_dict({"device": {"id": "basil-pi-01"}, "live": {"max_fps": 0}})


if __name__ == "__main__":
    unittest.main()
