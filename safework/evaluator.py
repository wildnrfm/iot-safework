"""Evaluator profil: ubah hasil deteksi satu frame menjadi status per APD.

Prinsip (sesuai dokumen rancangan):
  * Pelanggaran hanya dinyatakan bila ada BUKTI: kelas "tidak dipakai" (no_helmet, no_gloves, ...) terdeteksi.
  * Bila APD maupun kelas "tidak dipakai"-nya tidak terlihat, hasilnya "tidak dapat dipastikan",
    bukan pelanggaran.
  * Fungsi ini murni (tanpa kamera/model/jam) sehingga mudah diuji dengan data buatan.
"""
from __future__ import annotations

from typing import Iterable, Optional

from .labels import NEGATIVE_LABEL, PERSON, ZONES
from .schemas import (Detection, FrameEvaluation, ItemResult, ItemState, PpeRule, Profile, Requirement, Status)


def in_zone(det: Detection, person: Detection, item: str) -> bool:
    """Apakah pusat kotak deteksi berada di zona tubuh yang sesuai untuk APD `item`?"""
    y_min, y_max, x_margin = ZONES[item]
    px1, py1, px2, py2 = person.box
    w, h = px2 - px1, py2 - py1
    if w <= 0 or h <= 0:
        return False
    cx, cy = det.center
    return (px1 - x_margin * w <= cx <= px2 + x_margin * w) and (py1 + y_min * h <= cy <= py1 + y_max * h)


def filter_roi(detections: list[Detection], roi: Optional[tuple[float, float, float, float]],
               width: float, height: float) -> list[Detection]:
    """Buang deteksi yang pusatnya di luar area pemeriksaan (ROI = pecahan 0-1 dari lebar/tinggi frame).
    Berguna untuk mengabaikan latar belakang yang berantakan atau orang lain di luar penanda."""
    if roi is None:
        return detections
    x1, y1, x2, y2 = roi[0] * width, roi[1] * height, roi[2] * width, roi[3] * height
    return [d for d in detections if x1 <= d.center[0] <= x2 and y1 <= d.center[1] <= y2]


def _evaluate_item(rule: PpeRule, person: Detection, detections: list[Detection],
                   supported: Optional[set[str]], conf_pos: float,
                   conf_neg: float) -> tuple[ItemResult, list[Detection]]:
    """Mengembalikan status APD dan daftar deteksi yang dipakai sebagai bukti."""
    pos_label = rule.item
    neg_label = NEGATIVE_LABEL[rule.item]
    if supported is not None and pos_label not in supported and neg_label not in supported:
        return ItemResult(rule.item, rule.requirement, ItemState.UNCERTAIN, "kelas_tidak_didukung"), []

    pos = [d for d in detections if d.label == pos_label and d.conf >= conf_pos and in_zone(d, person, rule.item)]
    neg = [d for d in detections if d.label == neg_label and d.conf >= conf_neg and in_zone(d, person, rule.item)]
    used = pos + neg

    if pos and neg:
        return ItemResult(rule.item, rule.requirement, ItemState.UNCERTAIN, "bukti_bertentangan"), used
    if pos:
        return ItemResult(rule.item, rule.requirement, ItemState.MET, "terlihat"), used
    if neg:
        return ItemResult(rule.item, rule.requirement, ItemState.NOT_MET, "kelas_tidak_dipakai_terdeteksi"), used
    return ItemResult(rule.item, rule.requirement, ItemState.UNCERTAIN, "tidak_terlihat"), []


def evaluate(detections: list[Detection], profile: Profile, *, supported: Optional[set[str]] = None,
             conf_person: float = 0.5, conf_pos: float = 0.5, conf_neg: float = 0.35) -> FrameEvaluation:
    """Evaluasi satu frame. `supported` = himpunan label kanonis yang bisa dihasilkan model (None = semua)."""
    persons = [d for d in detections if d.label == PERSON and d.conf >= conf_person]
    if not persons:
        return FrameEvaluation(person_found=False)
    person = max(persons, key=lambda d: d.area)  # pos cek: satu pekerja, ambil yang terbesar di frame
    items: list[ItemResult] = []
    used: list[Detection] = []
    for rule in profile.rules:
        if rule.requirement == Requirement.NOT_NEEDED:
            continue
        item, evidence = _evaluate_item(rule, person, detections, supported, conf_pos, conf_neg)
        items.append(item)
        used.extend(evidence)
    return FrameEvaluation(person_found=True, items=tuple(items), person_box=person.box, used=tuple(used))


def overall_status(items: Iterable[ItemResult]) -> Status:
    """Status akhir dari status per APD. APD opsional tidak memengaruhi hasil."""
    required = [i for i in items if i.requirement == Requirement.REQUIRED]
    if any(i.state == ItemState.NOT_MET for i in required):
        return Status.INCOMPLETE
    if any(i.state == ItemState.UNCERTAIN for i in required):
        return Status.UNCERTAIN
    return Status.COMPLETE
