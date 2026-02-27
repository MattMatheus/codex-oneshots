from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass

import cv2

from .cv import LiveImpactDetector
from .storage import DartBoardStore


@dataclass
class CaptureState:
    running: bool = False
    preview_only: bool = False
    user_id: str | None = None
    session_id: str | None = None
    camera_index: int | None = None
    fps: int = 10
    frames_processed: int = 0
    throws_detected: int = 0
    last_error: str | None = None


class USBCaptureManager:
    def __init__(self, store: DartBoardStore) -> None:
        self.store = store
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = CaptureState()
        self._latest_frame: bytes | None = None
        self._frame_lock = threading.Lock()

    def status(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._state)

    def get_latest_frame(self) -> bytes | None:
        """Return the latest JPEG-encoded frame, or None if no frame available."""
        with self._frame_lock:
            return self._latest_frame

    def start_preview(self, camera_index: int = 0, fps: int = 10) -> dict[str, object]:
        """Start camera preview without recording data."""
        with self._lock:
            if self._state.running:
                raise RuntimeError("capture already running")
            self._stop_event.clear()
            self._state = CaptureState(
                running=True,
                preview_only=True,
                camera_index=camera_index,
                fps=fps,
            )
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(None, None, camera_index, fps, True),
                daemon=True,
            )
            self._thread.start()
            return asdict(self._state)

    def start_capture(self, user_id: str, session_id: str, camera_index: int = 0, fps: int = 10) -> dict[str, object]:
        with self._lock:
            if self._state.running:
                raise RuntimeError("capture already running")
            self._stop_event.clear()
            self._state = CaptureState(
                running=True,
                preview_only=False,
                user_id=user_id,
                session_id=session_id,
                camera_index=camera_index,
                fps=fps,
            )
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(user_id, session_id, camera_index, fps, False),
                daemon=True,
            )
            self._thread.start()
            return asdict(self._state)

    def stop_capture(self) -> dict[str, object]:
        thread = None
        with self._lock:
            self._stop_event.set()
            thread = self._thread

        if thread is not None:
            thread.join(timeout=2.0)

        with self._lock:
            self._state.running = False
            self._thread = None
            return asdict(self._state)

    def _run_loop(self, user_id: str | None, session_id: str | None, camera_index: int, fps: int, preview_only: bool = False) -> None:
        detector = LiveImpactDetector() if not preview_only else None
        interval_s = 1.0 / max(1, fps)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            with self._lock:
                self._state.running = False
                self._state.last_error = f"failed to open camera index {camera_index}"
            cap.release()
            return

        try:
            next_tick = time.monotonic()
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                # Crop frame to square (center crop)
                h, w = frame.shape[:2]
                if w > h:
                    offset = (w - h) // 2
                    frame = frame[:, offset:offset + h]
                elif h > w:
                    offset = (h - w) // 2
                    frame = frame[offset:offset + w, :]

                # Encode frame as JPEG for live streaming
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                with self._frame_lock:
                    self._latest_frame = jpeg.tobytes()

                # Only detect and record if not in preview mode
                if not preview_only and detector is not None and user_id and session_id:
                    hit = detector.detect_hit(frame)
                    with self._lock:
                        self._state.frames_processed += 1

                    if hit is not None:
                        self.store.add_throw(
                            user_id=user_id,
                            session_id=session_id,
                            x_norm=hit.x_norm,
                            y_norm=hit.y_norm,
                            confidence=hit.confidence,
                        )
                        with self._lock:
                            self._state.throws_detected += 1

                next_tick += interval_s
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_tick = time.monotonic()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._state.last_error = str(exc)
        finally:
            cap.release()
            with self._lock:
                self._state.running = False
            with self._frame_lock:
                self._latest_frame = None
