"""Indikator virtual: lampu dan buzzer ditampilkan di dashboard (tanpa hardware)."""
from __future__ import annotations

import threading

from .base import Indicator, Lamp


class VirtualIndicator(Indicator):
    """Menyimpan keadaan lampu. Dashboard membacanya lewat /api/state dan memainkan beep
    setiap kali `beep_seq` bertambah (naik tiap lampu berpindah ke merah)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lamp = Lamp.OFF
        self._beep_seq = 0
        self._test_seq = 0

    def set_lamp(self, lamp: Lamp) -> None:
        with self._lock:
            if lamp == Lamp.RED and self._lamp != Lamp.RED:
                self._beep_seq += 1
            self._lamp = lamp

    def test(self) -> None:
        with self._lock:
            self._test_seq += 1

    def info(self) -> dict:
        with self._lock:
            return {"lamp": self._lamp.value, "beep_seq": self._beep_seq, "test_seq": self._test_seq}
