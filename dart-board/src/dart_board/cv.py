from dataclasses import dataclass


@dataclass
class HitPoint:
    x_norm: float
    y_norm: float
    confidence: float


class VideoThrowDetector:
    """Stub detector.

    Replace with board calibration + impact detection/tracking implementation.
    """

    def detect_hits(self, video_source: str) -> list[HitPoint]:
        _ = video_source
        return []
