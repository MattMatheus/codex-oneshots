from __future__ import annotations

import io
import math

import cv2
import numpy as np


# Standard dartboard colors
BLACK = (30, 30, 30)
WHITE = (220, 215, 200)
RED = (40, 45, 180)
GREEN = (50, 100, 45)
WIRE = (120, 120, 120)

# Dartboard ring radii as fraction of board radius
DOUBLE_OUTER = 1.0
DOUBLE_INNER = 0.935
TRIPLE_OUTER = 0.63
TRIPLE_INNER = 0.565
OUTER_BULL = 0.16
INNER_BULL = 0.065


def _draw_dartboard(size: int) -> np.ndarray:
    """Draw a realistic dartboard background."""
    canvas = np.full((size, size, 3), 30, dtype=np.uint8)
    center = size // 2
    radius = int(size * 0.48)  # Board radius

    # Segment order (clockwise from top): 20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5
    segments = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
    segment_angle = 360 / 20
    start_angle = -99  # Offset so 20 is at top

    def get_segment_colors(idx: int) -> tuple:
        """Returns (main_color, double_triple_color) for segment index."""
        if idx % 2 == 0:
            return WHITE, RED
        else:
            return BLACK, GREEN

    # Draw outer black ring (outside the doubles)
    cv2.circle(canvas, (center, center), int(radius * 1.05), BLACK, thickness=-1)

    # Draw each segment
    for i, _ in enumerate(segments):
        main_color, special_color = get_segment_colors(i)
        angle_start = start_angle + i * segment_angle
        angle_end = angle_start + segment_angle

        # Draw double ring (outer)
        cv2.ellipse(canvas, (center, center), (int(radius * DOUBLE_OUTER), int(radius * DOUBLE_OUTER)),
                    0, angle_start, angle_end, special_color, thickness=-1)
        # Draw main outer section
        cv2.ellipse(canvas, (center, center), (int(radius * DOUBLE_INNER), int(radius * DOUBLE_INNER)),
                    0, angle_start, angle_end, main_color, thickness=-1)
        # Draw triple ring
        cv2.ellipse(canvas, (center, center), (int(radius * TRIPLE_OUTER), int(radius * TRIPLE_OUTER)),
                    0, angle_start, angle_end, special_color, thickness=-1)
        # Draw main inner section
        cv2.ellipse(canvas, (center, center), (int(radius * TRIPLE_INNER), int(radius * TRIPLE_INNER)),
                    0, angle_start, angle_end, main_color, thickness=-1)

    # Draw bullseye rings
    cv2.circle(canvas, (center, center), int(radius * OUTER_BULL), GREEN, thickness=-1)
    cv2.circle(canvas, (center, center), int(radius * INNER_BULL), RED, thickness=-1)

    # Draw wire lines (segment dividers)
    for i in range(20):
        angle_rad = math.radians(start_angle + i * segment_angle)
        x_end = int(center + radius * DOUBLE_OUTER * math.cos(angle_rad))
        y_end = int(center + radius * DOUBLE_OUTER * math.sin(angle_rad))
        cv2.line(canvas, (center, center), (x_end, y_end), WIRE, 1)

    # Draw wire rings
    for ring_frac in [DOUBLE_OUTER, DOUBLE_INNER, TRIPLE_OUTER, TRIPLE_INNER, OUTER_BULL, INNER_BULL]:
        cv2.circle(canvas, (center, center), int(radius * ring_frac), WIRE, 1)

    # Draw segment numbers
    number_radius = int(radius * 1.12)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = size / 800
    for i, num in enumerate(segments):
        angle_rad = math.radians(start_angle + (i + 0.5) * segment_angle)
        x = int(center + number_radius * math.cos(angle_rad))
        y = int(center + number_radius * math.sin(angle_rad))
        text = str(num)
        text_size = cv2.getTextSize(text, font, font_scale, 2)[0]
        cv2.putText(canvas, text, (x - text_size[0] // 2, y + text_size[1] // 2),
                    font, font_scale, WHITE, 2, cv2.LINE_AA)

    return canvas


def render_heatmap(points: list[tuple[float, float]], size: int = 640) -> bytes:
    base = _draw_dartboard(size)
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
