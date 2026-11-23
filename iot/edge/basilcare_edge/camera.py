"""Image sources: the Raspberry Pi camera, or a folder of pictures (development and tests)."""
import itertools
import threading
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


class PiCamera:
    """Raspberry Pi camera module through Picamera2 (installed with apt: python3-picamera2).

    Controls fixed in the config (exposure, white balance) give consistent pictures from one
    capture to the next, which the classifier needs (scope section 3.1: "consistent images of
    leaves under controlled lighting").
    """

    def __init__(self, width=1640, height=1232, controls=None):
        from picamera2 import Picamera2   # only on the Pi
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_still_configuration(main={"size": (width, height)}))
        if controls:
            self.camera.set_controls(dict(controls))
        self.camera.start()
        self.lock = threading.Lock()   # the live view and the screenings share the camera

    def capture(self):
        with self.lock:
            return self.camera.capture_image("main").convert("RGB")

    def close(self):
        self.camera.stop()
        self.camera.close()


class FolderCamera:
    """Returns the pictures of a folder one after the other, in a loop.

    Lets the whole screening chain (quality, model, MQTT, API, PWA) run on a laptop, or on the
    Pi with test pictures before the camera is mounted over the plants.
    """

    def __init__(self, folder):
        files = sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
        if not files:
            raise ValueError(f"no image in {folder}")
        self.files = itertools.cycle(files)
        self.lock = threading.Lock()

    def capture(self):
        with self.lock:
            path = next(self.files)
        with Image.open(path) as image:
            return image.convert("RGB")

    def close(self):
        pass


def open_camera(config):
    if config.source == "folder":
        return FolderCamera(config.folder_path)
    if config.source == "picamera2":
        return PiCamera(config.width, config.height, config.controls)
    raise ValueError(f"camera.source must be picamera2 or folder, not {config.source!r}")
