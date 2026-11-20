"""Antarmuka Indicator: satu tempat untuk lampu/buzzer, baik virtual (layar) maupun fisik (ESP32)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterable, Optional

from ..schemas import Status

log = logging.getLogger(__name__)


class Lamp(str, Enum):
    """Perintah indikator. Nilainya sama dengan perintah USB Serial ke ESP32."""
    OFF = "OFF"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    FAULT = "FAULT"     # kuning berkedip: kamera/koneksi bermasalah (mode aman)


STATUS_TO_LAMP = {
    Status.COMPLETE: Lamp.GREEN,
    Status.UNCERTAIN: Lamp.YELLOW,
    Status.INCOMPLETE: Lamp.RED,   # merah juga membunyikan buzzer
}


class Indicator(ABC):
    @abstractmethod
    def set_lamp(self, lamp: Lamp) -> None:
        """Nyalakan lampu sesuai perintah. Merah => buzzer berbunyi sebentar."""

    def show_status(self, status: Optional[Status]) -> None:
        """Tampilkan status pemeriksaan; None (menunggu/memeriksa) mematikan lampu."""
        self.set_lamp(STATUS_TO_LAMP[status] if status is not None else Lamp.OFF)

    def test(self) -> None:
        """Uji lampu dan buzzer."""

    def info(self) -> dict:
        """Status indikator untuk dashboard."""
        return {}

    def close(self) -> None:
        """Lepaskan sumber daya."""


class MultiIndicator(Indicator):
    """Gabungkan beberapa indikator (mis. virtual + ESP32). Kegagalan satu indikator tidak mengganggu yang lain."""

    def __init__(self, indicators: Iterable[Indicator]):
        self.indicators = list(indicators)

    def _each(self, method: str, *args) -> None:
        for ind in self.indicators:
            try:
                getattr(ind, method)(*args)
            except Exception:  # noqa: BLE001 - indikator tidak boleh menjatuhkan pipeline
                log.exception("Indikator %s gagal pada %s", type(ind).__name__, method)

    def set_lamp(self, lamp: Lamp) -> None:
        self._each("set_lamp", lamp)

    def test(self) -> None:
        self._each("test")

    def close(self) -> None:
        self._each("close")

    def info(self) -> dict:
        merged: dict = {}
        for ind in self.indicators:
            try:
                merged.update(ind.info())
            except Exception:  # noqa: BLE001
                log.exception("Indikator %s gagal pada info", type(ind).__name__)
        return merged
