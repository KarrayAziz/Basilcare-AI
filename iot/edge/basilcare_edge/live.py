"""Live camera view: capture -> detector -> small JPEG + detections -> MQTT, a few times a second.

Frames only exist in memory: nothing is written to the SD card and the cloud keeps only the
latest frame per device, in memory (contract section 6a). The 10-minute screenings stay the
record of the plant's health. Frames are published with QoS 0 and only while connected: a
lost or late frame is simply replaced by the next one, so they never fill the offline queue.
"""
import base64
import io
import logging
import time

from . import messages

log = logging.getLogger(__name__)


class LiveService:
    def __init__(self, device_id, camera, detector, max_fps=2.0, width=640, jpeg_quality=70,
                 clock=messages.local_now):
        self.device_id = device_id
        self.camera = camera
        self.detector = detector
        self.period = 1.0 / max_fps
        self.width = width
        self.jpeg_quality = jpeg_quality
        self.clock = clock
        self.frame_id = 0
        self.fps = 0.0

    def frame(self):
        """One frame -> (topic, payload, retain)."""
        captured_at = self.clock()
        image = self.camera.capture()
        if image.width > self.width:
            image = image.resize((self.width, round(image.height * self.width / image.width)))
        detections, inference_ms = self.detector.detect(image)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=self.jpeg_quality)
        self.frame_id += 1
        return messages.live_frame(self.device_id, self.frame_id, captured_at, self.detector.version,
                                   image.width, image.height, base64.b64encode(buffer.getvalue()).decode("ascii"),
                                   detections, inference_ms, self.fps)

    def run(self, publish, connected, stop):
        """Thread body. publish(topic, payload) sends with QoS 0; connected and stop are Events."""
        log.info("live camera view on: at most %.1f frames/s, %d px wide", 1 / self.period, self.width)
        last = None
        while not stop.is_set():
            if not connected.wait(0.5):   # wakes up as soon as the broker is back
                continue
            started = time.monotonic()
            try:
                topic, payload, _ = self.frame()
                publish(topic, payload)
            except Exception:
                log.exception("live frame failed")
                stop.wait(5)
                continue
            if last is not None:
                self.fps = 0.8 * self.fps + 0.2 * (1 / max(started - last, 1e-3)) if self.fps else 1 / max(started - last, 1e-3)
            last = started
            stop.wait(max(0.0, self.period - (time.monotonic() - started)))
