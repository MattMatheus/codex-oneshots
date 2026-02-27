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

    def status(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._state)

    def start_capture(self, user_id: str, session_id: str, camera_index: int = 0, fps: int = 10) -> dict[str, object]:
        with self._lock:
            if self._state.running:
                raise RuntimeError("capture already running")
            self._stop_event.clear()
            self._state = CaptureState(
                running=True,
                user_id=user_id,
                session_id=session_id,
                camera_index=camera_index,
                fps=fps,
            )
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(user_id, session_id, camera_index, fps),
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

    def _run_loop(self, user_id: str, session_id: str, camera_index: int, fps: int) -> None:
        detector = LiveImpactDetector()
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
