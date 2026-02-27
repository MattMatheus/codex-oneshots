from __future__ import annotations

import json
import threading
from pathlib import Path

import cv2
import numpy as np


class BoardCalibrator:
    def __init__(self, state_path: str = "calibration.json", target_size: int = 800) -> None:
        self.state_path = Path(state_path)
        self.target_size = target_size
        self._lock = threading.Lock()
        self._src_points: np.ndarray | None = None
        self._homography: np.ndarray | None = None
        self._load()

    def _dst_points(self) -> np.ndarray:
        s = float(self.target_size - 1)
        return np.array([[0, 0], [s, 0], [s, s], [0, s]], dtype=np.float32)

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            points = payload.get("src_points")
            if isinstance(points, list) and len(points) == 4:
                self._src_points = np.array(points, dtype=np.float32)
                self._homography = cv2.getPerspectiveTransform(self._src_points, self._dst_points())
        except Exception:
            self._src_points = None
            self._homography = None

    def _save(self) -> None:
        payload = {"src_points": self._src_points.tolist() if self._src_points is not None else None}
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def set_src_points(self, src_points: list[list[float]]) -> None:
        if len(src_points) != 4:
            raise ValueError("exactly 4 source points are required")

        src = np.array(src_points, dtype=np.float32)
        with self._lock:
            self._src_points = src
            self._homography = cv2.getPerspectiveTransform(self._src_points, self._dst_points())
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._src_points = None
            self._homography = None
            self._save()

    def is_calibrated(self) -> bool:
        with self._lock:
            return self._homography is not None

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "calibrated": self._homography is not None,
                "target_size": self.target_size,
                "src_points": self._src_points.tolist() if self._src_points is not None else None,
            }

    def transform_point(self, x_px: float, y_px: float) -> tuple[float, float] | None:
        with self._lock:
            if self._homography is None:
                return None
            src = np.array([[[x_px, y_px]]], dtype=np.float32)
            dst = cv2.perspectiveTransform(src, self._homography)
            x, y = float(dst[0, 0, 0]), float(dst[0, 0, 1])

        scale = float(max(1, self.target_size - 1))
        x_norm = max(0.0, min(1.0, x / scale))
        y_norm = max(0.0, min(1.0, y / scale))
        return (x_norm, y_norm)

    def warp_frame(self, frame) -> object:
        with self._lock:
            if self._homography is None:
                return frame
            return cv2.warpPerspective(frame, self._homography, (self.target_size, self.target_size))
