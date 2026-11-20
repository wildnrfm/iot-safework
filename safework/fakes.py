"""Sumber data palsu untuk mode simulasi, demo konsol, dan pengujian (tanpa kamera dan tanpa model)."""
from __future__ import annotations

import time
from typing import Callable, Iterable

from .labels import NEGATIVE_LABEL, PERSON, ZONES
from .schemas import Detection, Profile, Requirement

FRAME_W, FRAME_H = 1280, 720
PERSON_BOX = (500.0, 40.0, 780.0, 700.0)


def apd_box(item: str, person=PERSON_BOX) -> tuple[float, float, float, float]:
    """Kotak APD buatan yang pusatnya berada di zona tubuh yang benar."""
    x1, y1, x2, y2 = person
    w, h = x2 - x1, y2 - y1
    y_min, y_max, _ = ZONES[item]
    cy = y1 + h * (y_min + y_max) / 2.0
    cx = x1 + w * (0.15 if item == "gloves" else 0.5)
    half = w * (0.12 if item in ("gloves", "goggles", "mask") else 0.2)
    return (max(cx - half, 0.0), max(cy - half, 0.0), min(cx + half, FRAME_W - 1.0), min(cy + half, FRAME_H - 1.0))


def scene(present: Iterable[str] = (), absent: Iterable[str] = (), conf: float = 0.9,
          person=PERSON_BOX) -> list[Detection]:
    """Satu orang + APD yang terpasang (`present`) + kelas "tidak dipakai" (`absent`)."""
    dets = [Detection(PERSON, conf, person)]
    dets += [Detection(i, conf, apd_box(i, person)) for i in present]
    dets += [Detection(NEGATIVE_LABEL[i], conf, apd_box(i, person)) for i in absent]
    return dets


class ScriptedDetector:
    """Detektor palsu: bergantian menampilkan pekerja lengkap, melanggar, dan APD tidak terlihat jelas."""

    supported_labels = None  # semua label dianggap didukung
    supports_crop = False    # koordinatnya mutlak (bukan hasil membaca gambar), jangan dipotong
    SCENARIOS = ("Lengkap", "APD pertama terbukti tidak dipakai", "APD terakhir tidak terlihat")

    def __init__(self, profile_getter: Callable[[], Profile], present_seconds: float = 10.0,
                 gap_seconds: float = 4.0, clock: Callable[[], float] = time.monotonic):
        self._profile_getter = profile_getter
        self.present_seconds = present_seconds
        self.gap_seconds = gap_seconds
        self._clock = clock
        self._t0 = clock()
        self.scenario = ""

    def detect(self, frame=None) -> list[Detection]:
        t = self._clock() - self._t0
        cycle = self.present_seconds + self.gap_seconds
        index, offset = int(t // cycle), t % cycle
        if offset >= self.present_seconds:
            self.scenario = "Tidak ada orang"
            return []
        profile = self._profile_getter()
        required = [r.item for r in profile.rules if r.requirement == Requirement.REQUIRED]
        optional = [r.item for r in profile.rules if r.requirement == Requirement.OPTIONAL]
        present = set(required) | set(optional)
        absent: set[str] = set()
        n = index % 3
        self.scenario = self.SCENARIOS[n]
        if required and n == 1:
            present.discard(required[0])
            absent.add(required[0])
        elif required and n == 2:
            present.discard(required[-1])
        return scene(present, absent)


class SyntheticSource:
    """Pengganti kamera: frame gelap dengan teks, supaya dashboard punya gambar untuk ditampilkan."""

    def __init__(self, width: int = FRAME_W, height: int = FRAME_H):
        import cv2
        import numpy as np

        self._frame = np.full((height, width, 3), (46, 38, 30), dtype=np.uint8)
        cv2.putText(self._frame, "MODE SIMULASI - tanpa kamera", (24, height - 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 170, 160), 2, cv2.LINE_AA)

    def read(self):
        return self._frame.copy()

    def close(self) -> None:
        pass
