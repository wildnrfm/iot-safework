#!/usr/bin/env python
"""Peluncur SAFEWORK AI: deteksi ESP32 dan kamera otomatis, lalu jalankan aplikasi.

Pakai (dari folder utama proyek):
    python scripts\\jalankan.py
    python scripts\\jalankan.py --dry-run      hanya cetak perintah, tidak menjalankan
    python scripts\\jalankan.py --camera 1 --serial COM5    paksa kamera dan port

Peluncur hanya memakai opsi yang ada di README: --weights, --camera, --camera-backend, --serial, --roi, --debug.
"""
import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VID_USB_SERIAL = {0x10C4: "CP210x", 0x1A86: "CH340/CH9102", 0x0403: "FTDI"}


def nomor_port(device):
    m = re.search(r"(\d+)$", str(device))
    return int(m.group(1)) if m else -1


def pilih_port(ports):
    """ports: objek dengan .device dan .vid. Mengembalikan device ESP32 (jembatan USB-serial dikenal), atau None.
    Bila ada beberapa, dipilih nomor COM tertinggi (perangkat yang baru dicolok biasanya mendapat nomor lebih tinggi)."""
    cocok = [p for p in ports if getattr(p, "vid", None) in VID_USB_SERIAL]
    if not cocok:
        return None
    return max(cocok, key=lambda p: nomor_port(p.device)).device


def pilih_kamera(hasil):
    """hasil: daftar (indeks, lebar, tinggi). Pilih lebar terbesar; bila seri, indeks lebih tinggi
    (webcam eksternal biasanya terdaftar setelah kamera bawaan)."""
    if not hasil:
        return None
    return max(hasil, key=lambda h: (h[1], h[0]))[0]


def deteksi_port():
    try:
        from serial.tools import list_ports
    except ImportError:
        print("pyserial belum terpasang; port ESP32 tidak bisa dideteksi.")
        return []
    return list(list_ports.comports())


def deteksi_kamera(maks=4):
    os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")  # indeks kamera yang tidak ada tidak perlu memenuhi layar dengan log
    try:
        import cv2
    except ImportError:
        print("OpenCV belum terpasang; kamera tidak bisa dideteksi.")
        return []
    hasil = []
    for i in range(maks):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(i)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            hasil.append((i, w, h))
        cap.release()
    return hasil


def susun_perintah(weights, roi, kamera, port, debug):
    cmd = [sys.executable, "-m", "safework", "--weights", str(weights), "--camera", str(kamera), "--roi", roi]
    if os.name == "nt":
        cmd += ["--camera-backend", "dshow"]
    if port:
        cmd += ["--serial", port]
    if debug:
        cmd.append("--debug")
    return cmd


def main(argv=None):
    ap = argparse.ArgumentParser(description="Peluncur SAFEWORK AI (deteksi otomatis ESP32 dan kamera)")
    ap.add_argument("--weights", default=str(Path("runs") / "ppe-v2-ft1" / "weights" / "best.pt"))
    ap.add_argument("--roi", default="0.25,0,0.75,1")
    ap.add_argument("--camera", type=int, help="paksa nomor kamera (lewati deteksi)")
    ap.add_argument("--serial", help="paksa port ESP32, mis. COM5 (lewati deteksi)")
    ap.add_argument("--tanpa-indikator", action="store_true", help="jalan tanpa ESP32")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="hanya cetak perintah")
    args = ap.parse_args(argv)

    weights = Path(args.weights)
    if not weights.is_absolute():
        weights = ROOT / weights
    if not weights.exists():
        print(f"Bobot model tidak ditemukan: {weights}")
        return 2

    kamera = args.camera
    if kamera is None:
        hasil = deteksi_kamera()
        kamera = pilih_kamera(hasil)
        if kamera is None:
            print("Tidak ada kamera yang terbaca. Cek kabel dan hub, lalu coba lagi atau pakai --camera N.")
            return 2
        print("Kamera terdeteksi:", ", ".join(f"{i} ({w}x{h})" for i, w, h in hasil), f"-> dipakai {kamera}")

    port = None
    if not args.tanpa_indikator:
        port = args.serial or pilih_port(deteksi_port())
        if port is None:
            print("ESP32 tidak terdeteksi. Cek kabel dan driver, atau pakai --serial COMx. "
                  "Untuk jalan tanpa lampu dan buzzer, tambahkan --tanpa-indikator.")
            return 2
        print("ESP32:", port)

    env = os.environ.copy()
    if not env.get("SAFEWORK_ADMIN_TOKEN"):
        env["SAFEWORK_ADMIN_TOKEN"] = secrets.token_urlsafe(8)
        print("Token admin untuk sesi ini (dipakai di dashboard):", env["SAFEWORK_ADMIN_TOKEN"])

    cmd = susun_perintah(weights, args.roi, kamera, port, args.debug)
    print("Perintah:", " ".join(cmd))
    if args.dry_run:
        return 0
    print("Dashboard: http://127.0.0.1:8000  (hentikan dengan Ctrl+C)")
    try:
        return subprocess.run(cmd, cwd=ROOT, env=env).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
