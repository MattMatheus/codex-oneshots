from __future__ import annotations

import time
from dataclasses import dataclass

import cv2


@dataclass
class HitPoint:
    x_norm: float
    y_norm: float
    confidence: float


class LiveImpactDetector:
    """Lightweight motion-based hit detector for MVP live capture.

    This is a placeholder until board-calibrated dart-impact detection is implemented.
    """

    def __init__(self, min_motion_area: int = 1200, cooldown_s: float = 0.35) -> None:
        self.min_motion_area = min_motion_area
        self.cooldown_s = cooldown_s
        self._prev_gray = None
        self._last_hit_ts = 0.0

    def detect_hit(self, frame) -> HitPoint | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return None

        diff = cv2.absdiff(self._prev_gray, gray)
        _, thresh = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self._prev_gray = gray

        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        if area < self.min_motion_area:
            return None

        now = time.monotonic()
        if now - self._last_hit_ts < self.cooldown_s:
            return None

        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            return None

        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]

        h, w = gray.shape
        x_norm = max(0.0, min(1.0, cx / max(w - 1, 1)))
        y_norm = max(0.0, min(1.0, cy / max(h - 1, 1)))

        confidence = min(1.0, area / float(max(1, w * h * 0.02)))
        self._last_hit_ts = now
        return HitPoint(x_norm=x_norm, y_norm=y_norm, confidence=confidence)
