"""Pengaturan aplikasi (argumen baris perintah)."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    fake: bool = False
    weights: str = "yolo11n.pt"            # ganti dengan best.pt hasil latihan
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_backend: str = "auto"           # auto | dshow | msmf | v4l2
    serial_port: Optional[str] = None      # mis. COM5 atau /dev/ttyUSB0; kosong = tanpa ESP32
    data_dir: str = "data"
    host: str = "127.0.0.1"                # jangan ubah ke 0.0.0.0 tanpa autentikasi dan enkripsi
    port: int = 8000
    access_log: bool = False               # log tiap permintaan HTTP; dashboard polling 2x/detik, jadi mati bawaan
    conf: float = 0.25                     # ambang minimum keluaran model
    conf_person: float = 0.5
    conf_pos: float = 0.5                  # APD terpasang: ketat, karena salah hijau berbahaya
    conf_neg: float = 0.35                 # "tidak dipakai": lebih longgar (recall model rendah), dijaga pemungutan suara
    roi: Optional[tuple[float, float, float, float]] = None   # area pemeriksaan: x1,y1,x2,y2 (pecahan 0-1)
    debug: bool = False
    roi_crop: bool = True                  # potong frame ke ROI sebelum deteksi
    target_fps: float = 10.0
    admin_token: Optional[str] = None
    retention_days: int = 30               # masa simpan riwayat; 0 = tidak dihapus otomatis
    confirm_frames: int = 4
    violation_votes: int = 3
    window_frames: int = 10
    check_seconds: float = 3.0
    min_check_seconds: float = 1.0
    hold_seconds: float = 6.0
    absent_seconds: float = 1.5

    @classmethod
    def from_args(cls, argv: Optional[list[str]] = None) -> "Settings":
        d = cls()
        p = argparse.ArgumentParser(prog="python -m safework", description="SAFEWORK AI - Pos Cek APD Cerdas")
        p.add_argument("--fake", action="store_true", help="mode simulasi: tanpa kamera dan tanpa model")
        p.add_argument("--weights", default=d.weights, help="berkas bobot YOLO (.pt)")
        p.add_argument("--camera", type=int, default=d.camera_index, help="indeks kamera")
        p.add_argument("--camera-backend", default=d.camera_backend, choices=["auto", "dshow", "msmf", "v4l2"])
        p.add_argument("--serial", default=d.serial_port, help="port ESP32, mis. COM5 atau /dev/ttyUSB0")
        p.add_argument("--data-dir", default=d.data_dir)
        p.add_argument("--host", default=d.host)
        p.add_argument("--port", type=int, default=d.port)
        p.add_argument("--fps", type=float, default=d.target_fps, help="target FPS pemrosesan")
        p.add_argument("--access-log", action="store_true", help="tampilkan log tiap permintaan HTTP")
        p.add_argument("--conf-person", type=float, default=d.conf_person, help="ambang keyakinan orang")
        p.add_argument("--conf-pos", type=float, default=d.conf_pos, help="ambang keyakinan APD terpasang")
        p.add_argument("--conf-neg", type=float, default=d.conf_neg, help='ambang keyakinan kelas "tidak dipakai"')
        p.add_argument("--roi", nargs="+", default=None, metavar="ANGKA",
                       help='area pemeriksaan: empat angka 0-1 (x1,y1,x2,y2), mis. --roi "0.25,0,0.75,1" '
                            'atau --roi 0.25 0 0.75 1 (PowerShell memecah koma tanpa tanda kutip, keduanya diterima)')
        p.add_argument("--no-roi-crop", action="store_true",
                       help="jangan memotong frame ke ROI sebelum deteksi (ROI hanya menyaring hasil)")
        p.add_argument("--debug", action="store_true",
                       help="gambar zona APD dan keterangan bukti pada video (untuk kalibrasi)")
        a = p.parse_args(argv)
        roi = None
        if a.roi:
            try:
                roi = tuple(float(v) for v in ",".join(a.roi).split(",") if v.strip())
            except ValueError:
                p.error("--roi harus berisi empat angka dipisah koma, mis. 0.25,0,0.75,1")
            if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
                p.error("--roi harus x1,y1,x2,y2 dengan 0 <= x1 < x2 <= 1 dan 0 <= y1 < y2 <= 1")
        data_dir = a.data_dir
        if a.fake and data_dir == d.data_dir:
            data_dir = "data_sim"   # simulasi punya riwayat sendiri, supaya data nyata tidak tercampur
        return cls(
            fake=a.fake, weights=a.weights, camera_index=a.camera, camera_backend=a.camera_backend,
            serial_port=a.serial, data_dir=data_dir, host=a.host, port=a.port, target_fps=a.fps,
            access_log=a.access_log, conf_person=a.conf_person, conf_pos=a.conf_pos, conf_neg=a.conf_neg,
            roi=roi, debug=a.debug, roi_crop=not a.no_roi_crop,
            admin_token=os.environ.get("SAFEWORK_ADMIN_TOKEN") or None,
        )
