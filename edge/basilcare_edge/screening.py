"""One edge screening: capture -> quality checks -> model -> keep the image -> MQTT message.

Images stay on the Pi (contract section 6, scope section 4.1); only the derived result is sent.
The result is never a diagnosis: it is flagged review_required when the model is unsure,
when the image quality is poor, or when no model is installed yet (scope section 5.1).
"""
import logging
from pathlib import Path

from . import messages, quality

log = logging.getLogger(__name__)


class ScreeningService:
    def __init__(self, device_id, camera, classifier, images_dir, keep_images=500, review_threshold=0.7,
                 clock=messages.local_now):
        self.device_id = device_id
        self.camera = camera
        self.classifier = classifier
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.keep_images = keep_images
        self.review_threshold = review_threshold
        self.clock = clock

    def run(self):
        captured_at = self.clock()
        image = self.camera.capture()
        image_id = f"{self.device_id}-{captured_at:%Y%m%dT%H%M%S}"
        issues, measures = quality.assess(image)
        prediction = self.classifier.classify(image)
        review = (bool(issues) or prediction.label == "unknown"
                  or prediction.confidence < self.review_threshold)
        image.save(self.images_dir / f"{image_id}.jpg", quality=90)
        self._prune()
        log.info("screening %s: %s %.2f issues=%s review=%s (%.0f ms) %s", image_id, prediction.label,
                 prediction.confidence, issues, review, prediction.latency_ms,
                 {k: round(v, 3) for k, v in measures.items()})
        return messages.screening(self.device_id, image_id, captured_at, self.classifier.version,
                                  prediction.label, prediction.confidence, issues, review)

    def _prune(self):
        images = sorted(self.images_dir.glob("*.jpg"))
        for old in images[:-self.keep_images] if self.keep_images > 0 else []:
            old.unlink(missing_ok=True)
