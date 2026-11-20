"""Gambar kotak deteksi dan status pada frame untuk stream dashboard. Membutuhkan OpenCV."""
from __future__ import annotations

from .checkpoint import Snapshot
from .schemas import Detection, Phase, Status

# Warna BGR
NAVY = (93, 54, 23)
GREEN = (77, 115, 38)
RED = (60, 60, 200)
AMBER = (30, 160, 230)
GRAY = (110, 110, 110)


def band_color(snap: Snapshot) -> tuple[int, int, int]:
    if snap.phase == Phase.RESULT:
        return {Status.COMPLETE: GREEN, Status.INCOMPLETE: RED, Status.UNCERTAIN: AMBER}[snap.status]
    if snap.phase == Phase.FAULT:
        return RED
    if snap.phase == Phase.CHECKING:
        return NAVY
    return GRAY


def draw_overlay(frame, detections: list[Detection], headline: str, snap: Snapshot, used=(), subject_box=None,
                 roi_px=None, zones=(), debug: bool = False) -> None:
    """Gambar langsung pada `frame` (numpy BGR). Teks hanya ASCII karena cv2.putText tidak mendukung UTF-8.

    Kotak TEBAL = dipakai sebagai bukti (orang yang dinilai, atau APD yang lolos ambang dan zona).
    Kotak TIPIS berlatar abu-abu = terdeteksi tetapi diabaikan (keyakinan di bawah ambang, di luar zona,
    di luar area pemeriksaan, atau orang lain).
    """
    import cv2

    font = cv2.FONT_HERSHEY_SIMPLEX
    if roi_px is not None:
        rx1, ry1, rx2, ry2 = roi_px
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (200, 200, 60), 1)
        cv2.putText(frame, "area pemeriksaan", (rx1 + 6, ry2 - 8), font, 0.5, (200, 200, 60), 1, cv2.LINE_AA)
    for name, (zx1, zy1, zx2, zy2) in zones:
        cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), AMBER, 1)
        cv2.putText(frame, f"zona {name}", (zx1 + 3, zy1 + 14), font, 0.45, AMBER, 1, cv2.LINE_AA)

    used_set = list(used)
    for d in detections:
        x1, y1, x2, y2 = (int(v) for v in d.box)
        is_subject = d.label == "person" and subject_box is not None and tuple(d.box) == tuple(subject_box)
        strong = is_subject or d in used_set
        color = NAVY if d.label == "person" else (RED if d.label.startswith("no_") else GREEN)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3 if strong else 1)
        label = f"{d.label} {d.conf:.2f}"
        (tw, th), base = cv2.getTextSize(label, font, 0.55, 2)
        bottom = max(y1, 44 + th + base + 4)       # di atas kotak; bila mentok, di bawah pita status
        cv2.rectangle(frame, (x1, bottom - th - base - 4), (x1 + tw + 8, bottom), color if strong else (90, 90, 90), -1)
        cv2.putText(frame, label, (x1 + 4, bottom - base - 2), font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 44), band_color(snap), -1)
    cv2.putText(frame, headline, (14, 31), font, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    if debug:
        cv2.putText(frame, "DEBUG: kotak tebal = dipakai sebagai bukti, tipis abu-abu = diabaikan",
                    (10, frame.shape[0] - 12), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def encode_jpeg(frame, quality: int = 75) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("Gagal meng-encode JPEG")
    return buf.tobytes()
