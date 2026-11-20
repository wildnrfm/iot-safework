"""Teks yang ditampilkan pada layar/dashboard. Dipusatkan di sini agar frontend apa pun bisa memakainya."""
from __future__ import annotations

from .checkpoint import Snapshot
from .labels import ITEM_NAMES_ID
from .schemas import ItemResult, ItemState, Phase, Requirement, Status

FAULT_TEXT = {
    "kamera_terputus": ("Kamera terputus", "Periksa kabel kamera. Pemeriksaan lanjut otomatis setelah gambar kembali."),
    "deteksi_gagal": ("Deteksi gagal", "Periksa berkas model dan log aplikasi."),
}


def _names(items: tuple[ItemResult, ...], state: ItemState) -> str:
    return ", ".join(ITEM_NAMES_ID.get(i.item, i.item) for i in items
                     if i.requirement == Requirement.REQUIRED and i.state == state)


def headline_detail(snap: Snapshot) -> tuple[str, str]:
    if snap.phase == Phase.FAULT:
        return FAULT_TEXT.get(snap.fault, ("Gangguan sistem", "Periksa kamera, model, dan kabel."))
    if snap.phase == Phase.WAITING:
        return ("Menunggu pekerja", "Berdiri di penanda dan hadap kamera.")
    if snap.phase == Phase.CHECKING:
        return ("Memeriksa APD", "Tetap berdiri dan biarkan tangan serta kaki terlihat.")
    if snap.status == Status.COMPLETE:
        return ("Lengkap", "Pemeriksaan visual terpenuhi.")
    if snap.status == Status.INCOMPLETE:
        detail = "Lengkapi: " + _names(snap.items, ItemState.NOT_MET) + "."
        unsure = _names(snap.items, ItemState.UNCERTAIN)
        if unsure:
            detail += " Belum terlihat jelas: " + unsure + "."
        return ("Belum lengkap", detail)
    return ("Tidak dapat dipastikan",
            "Tidak terlihat jelas: " + _names(snap.items, ItemState.UNCERTAIN) +
            ". Perbaiki posisi atau pencahayaan, atau minta pendamping memeriksa.")
