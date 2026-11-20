"""Tipe data inti: deteksi, profil APD, hasil per APD, dan hasil pemeriksaan."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .labels import ITEM_NAMES_ID


class Requirement(str, Enum):
    REQUIRED = "wajib"
    OPTIONAL = "opsional"
    NOT_NEEDED = "tidak_diperlukan"


class ItemState(str, Enum):
    MET = "terpenuhi"
    NOT_MET = "tidak_terpenuhi"
    UNCERTAIN = "tidak_dapat_dipastikan"


class Status(str, Enum):
    """Hasil akhir satu pemeriksaan."""
    COMPLETE = "lengkap"
    INCOMPLETE = "belum_lengkap"
    UNCERTAIN = "tidak_dapat_dipastikan"


class Phase(str, Enum):
    WAITING = "menunggu"
    CHECKING = "memeriksa"
    RESULT = "hasil"
    FAULT = "gangguan"


@dataclass(frozen=True)
class Detection:
    label: str                                  # label kanonis (lihat labels.py)
    conf: float
    box: tuple[float, float, float, float]      # x1, y1, x2, y2 (piksel)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.box
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


@dataclass(frozen=True)
class PpeRule:
    item: str
    requirement: Requirement = Requirement.REQUIRED


@dataclass
class Profile:
    id: str
    name: str
    rules: list[PpeRule] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rules": [{"item": r.item, "requirement": r.requirement.value} for r in self.rules],
        }


@dataclass(frozen=True)
class ItemResult:
    item: str
    requirement: Requirement
    state: ItemState
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "item": self.item,
            "name": ITEM_NAMES_ID.get(self.item, self.item),
            "requirement": self.requirement.value,
            "state": self.state.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FrameEvaluation:
    """Hasil evaluasi satu frame (belum dikonfirmasi lintas frame)."""
    person_found: bool
    items: tuple[ItemResult, ...] = ()
    person_box: Optional[tuple[float, float, float, float]] = None
    used: tuple[Detection, ...] = ()    # deteksi yang benar-benar dipakai sebagai bukti (lolos ambang dan zona)


@dataclass(frozen=True)
class CheckResult:
    """Hasil akhir satu pemeriksaan di pos cek."""
    status: Status
    profile_id: str
    profile_name: str
    items: tuple[ItemResult, ...]
    missing: tuple[str, ...]        # APD wajib yang terbukti tidak dipakai
    uncertain: tuple[str, ...]      # APD wajib yang tidak dapat dipastikan
    started_at: float
    finished_at: float

    @property
    def duration(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "items": [i.to_dict() for i in self.items],
            "missing": list(self.missing),
            "uncertain": list(self.uncertain),
            "duration": round(self.duration, 2),
        }
