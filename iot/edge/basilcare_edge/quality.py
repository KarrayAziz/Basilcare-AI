"""Image-quality checks run before a screening result is trusted (scope section 5.1).

A model fed a dark, blurry or empty picture still outputs a confident-looking answer. These
cheap checks catch the usual capture problems so the result is flagged "review required"
instead of being shown as if it were reliable.

Issues (contract section 6, quality_issues):
  too_dark, too_bright, low_contrast, blurry, out_of_frame (almost no green leaf visible)
"""
import numpy as np

# Thresholds for a picture scaled to WORK_WIDTH pixels wide. Tune them on real captures
# (tools/capture_dataset.py) under the prototype's lighting.
WORK_WIDTH = 320
MIN_BRIGHTNESS = 40
MAX_BRIGHTNESS = 215
MIN_CONTRAST = 18
MIN_SHARPNESS = 60.0     # variance of the Laplacian
MIN_GREEN_FRACTION = 0.05


def _laplacian_variance(gray):
    lap = (gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1])
    return float(lap.var())


def measure(image):
    """Returns the raw measurements of a PIL image, for tuning and for the logs."""
    if image.width > WORK_WIDTH:
        image = image.resize((WORK_WIDTH, max(1, round(image.height * WORK_WIDTH / image.width))))
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = (g > r * 1.05) & (g > b * 1.05) & (g > 40)
    return {
        "brightness": float(gray.mean()),
        "contrast": float(gray.std()),
        "sharpness": _laplacian_variance(gray),
        "green_fraction": float(green.mean()),
    }


def assess(image):
    """Returns (issues, measurements). No issue = quality_ok."""
    m = measure(image)
    issues = []
    if m["brightness"] < MIN_BRIGHTNESS:
        issues.append("too_dark")
    elif m["brightness"] > MAX_BRIGHTNESS:
        issues.append("too_bright")
    if m["contrast"] < MIN_CONTRAST:
        issues.append("low_contrast")
    if m["sharpness"] < MIN_SHARPNESS:
        issues.append("blurry")
    if m["green_fraction"] < MIN_GREEN_FRACTION:
        issues.append("out_of_frame")
    return issues, m
