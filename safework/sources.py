"""Sumber gambar: kamera USB lewat OpenCV."""
from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


class Camera:
    """Webcam USB. `read()` mengembalikan None bila gagal; kamera dibuka ulang otomatis setelah beberapa kegagalan."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720, backend: str = "auto",
                 reopen_every: float = 2.0):
        self.index = index
        self.width = width
        self.height = height
        self.backend = backend
        self.reopen_every = reopen_every
        self._cap = None
        self._next_open = 0.0
        self._fails = 0

    def _open(self):
        import cv2

        apis = {
            "auto": cv2.CAP_ANY,
            "dshow": getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),   # Windows: biasanya paling cepat terbuka
            "msmf": getattr(cv2, "CAP_MSMF", cv2.CAP_ANY),
            "v4l2": getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),     # Linux
        }
        cap = cv2.VideoCapture(self.index, apis.get(self.backend, cv2.CAP_ANY))
        if not cap.isOpened():
            cap.release()
            return None
        # MJPG + 720p menghemat bandwidth USB (penting bila lewat hub) dan beban CPU.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return cap

    def read(self):
        now = time.monotonic()
        if self._cap is None:
            if now < self._next_open:
                return None
            self._cap = self._open()
            if self._cap is None:
                self._next_open = now + self.reopen_every
                log.warning("Kamera %s belum bisa dibuka", self.index)
                return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._fails += 1
            if self._fails >= 3:
                self._cap.release()
                self._cap = None
                self._fails = 0
                self._next_open = now + self.reopen_every
            return None
        self._fails = 0
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
