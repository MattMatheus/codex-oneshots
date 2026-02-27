from __future__ import annotations

import io

import cv2
import numpy as np


def _board_background(size: int) -> np.ndarray:
    canvas = np.full((size, size, 3), 24, dtype=np.uint8)
    center = (size // 2, size // 2)

    ring_colors = [
        (35, 35, 35),
        (55, 55, 55),
        (40, 90, 40),
        (90, 40, 40),
        (50, 50, 50),
    ]
    ring_radii = [0.48, 0.40, 0.30, 0.20, 0.08]

    for color, frac in zip(ring_colors, ring_radii):
        radius = int(size * frac)
        cv2.circle(canvas, center, radius, color, thickness=-1)

    cv2.circle(canvas, center, int(size * 0.03), (30, 150, 30), thickness=-1)
    cv2.circle(canvas, center, int(size * 0.015), (20, 20, 180), thickness=-1)
    return canvas


def render_heatmap(points: list[tuple[float, float]], size: int = 640) -> bytes:
    base = _board_background(size)
    acc = np.zeros((size, size), dtype=np.float32)

    for x_norm, y_norm in points:
        x = int(np.clip(x_norm, 0.0, 1.0) * (size - 1))
        y = int(np.clip(y_norm, 0.0, 1.0) * (size - 1))
        cv2.circle(acc, (x, y), int(size * 0.03), 1.0, thickness=-1)

    if np.max(acc) > 0:
        acc = cv2.GaussianBlur(acc, (0, 0), sigmaX=size * 0.02, sigmaY=size * 0.02)
        acc = acc / np.max(acc)
        heat = cv2.applyColorMap((acc * 255).astype(np.uint8), cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(base, 0.55, heat, 0.45, 0)
    else:
        overlay = base

    success, buf = cv2.imencode(".png", overlay)
    if not success:
        raise RuntimeError("failed to encode heatmap")

    return io.BytesIO(buf.tobytes()).getvalue()
