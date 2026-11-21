"""Profil pekerjaan: validasi, profil bawaan, dan penyimpanan JSON."""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from .labels import APD_ITEMS
from .schemas import PpeRule, Profile, Requirement

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def default_profiles() -> list[Profile]:
    required = Requirement.REQUIRED
    optional = Requirement.OPTIONAL
    return [
        Profile(
            id="penyemprot-pestisida",
            name="Penyemprot Pestisida",
            description="Contoh konfigurasi. Sesuaikan dengan label produk dan penilaian risiko.",
            rules=[PpeRule("mask", required), PpeRule("gloves", required),
                   PpeRule("goggles", required), PpeRule("boots", required)],
        ),
        Profile(
            id="pekerja-proyek-desa",
            name="Pekerja Proyek Desa",
            description="Contoh konfigurasi. Sesuaikan dengan aktivitas dan bahaya di lokasi.",
            rules=[PpeRule("helmet", required), PpeRule("vest", required),
                   PpeRule("boots", required), PpeRule("gloves", required),
                   PpeRule("goggles", optional)],
        ),
    ]


def parse_profile(data: dict) -> Profile:
    """Validasi data profil dari API/JSON. Melempar ValueError bila tidak valid."""
    pid = str(data.get("id", "")).strip().lower()
    if not _ID_RE.match(pid) or len(pid) > 40:
        raise ValueError("ID profil hanya boleh huruf kecil, angka, dan tanda hubung (maksimal 40 karakter).")
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 60:
        raise ValueError("Nama profil wajib diisi (maksimal 60 karakter).")
    rules: list[PpeRule] = []
    seen: set[str] = set()
    for raw in data.get("rules", []):
        item = str(raw.get("item", "")).strip().lower()
        if item not in APD_ITEMS:
            raise ValueError(f"APD '{item}' tidak dikenal. Pilihan: {', '.join(APD_ITEMS)}.")
        if item in seen:
            raise ValueError(f"APD '{item}' muncul lebih dari sekali.")
        seen.add(item)
        try:
            req = Requirement(str(raw.get("requirement", "wajib")).strip().lower())
        except ValueError:
            raise ValueError("Status APD harus salah satu dari: wajib, opsional, tidak_diperlukan.") from None
        rules.append(PpeRule(item, req))
    return Profile(id=pid, name=name, rules=rules, description=str(data.get("description", ""))[:200])


class ProfileStore:
    """Daftar profil + profil aktif, disimpan di satu berkas JSON."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._profiles: dict[str, Profile] = {}
        self._active = ""
        self._load()

    def _load(self) -> None:
        with self._lock:
            try:
                if self.path.exists():
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                    for raw in data.get("profiles", []):
                        p = parse_profile(raw)
                        self._profiles[p.id] = p
                    self._active = str(data.get("active", ""))
            except (OSError, ValueError, AttributeError):
                self._profiles = {}
            if not self._profiles:
                for p in default_profiles():
                    self._profiles[p.id] = p
                self._active = next(iter(self._profiles))
                self._save()
            elif self._active not in self._profiles:
                self._active = next(iter(self._profiles))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"active": self._active, "profiles": [p.to_dict() for p in self._profiles.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def list(self) -> list[Profile]:
        with self._lock:
            return list(self._profiles.values())

    def get(self, pid: str) -> Profile:
        with self._lock:
            return self._profiles[pid]

    @property
    def active_id(self) -> str:
        with self._lock:
            return self._active

    def active(self) -> Profile:
        with self._lock:
            return self._profiles[self._active]

    def set_active(self, pid: str) -> Profile:
        with self._lock:
            if pid not in self._profiles:
                raise KeyError(pid)
            self._active = pid
            self._save()
            return self._profiles[pid]

    def upsert(self, data: dict) -> Profile:
        profile = parse_profile(data)
        with self._lock:
            self._profiles[profile.id] = profile
            self._save()
        return profile

    def delete(self, pid: str) -> None:
        with self._lock:
            if pid not in self._profiles:
                raise KeyError(pid)
            if len(self._profiles) == 1:
                raise ValueError("Minimal harus ada satu profil.")
            del self._profiles[pid]
            if self._active == pid:
                self._active = next(iter(self._profiles))
            self._save()
