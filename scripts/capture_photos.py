"""Ambil foto lokal dari webcam untuk data latih/uji.  SPASI = simpan foto, Q = keluar.

    python scripts/capture_photos.py --scene lengkap --out data_local/raw
    python scripts/capture_photos.py --scene tanpa-sarung-tangan --camera 1

Etika data: minta persetujuan orang yang difoto, hindari merekam identitas (wajah, kartu nama),
dan simpan hanya di perangkatmu. Ambil contoh LENGKAP dan TIDAK LENGKAP, dengan variasi jarak,
sudut, pencahayaan, dan orang. Nama file memuat nama adegan agar mudah disaring saat anotasi.
"""
import argparse
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="adegan", help="nama adegan, mis. lengkap atau tanpa-sarung-tangan")
    ap.add_argument("--out", default="data_local/raw")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()

    import cv2

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(a.camera)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    if not cap.isOpened():
        raise SystemExit("Kamera tidak bisa dibuka. Coba --camera 1 atau periksa izin kamera.")

    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        view = frame.copy()
        cv2.putText(view, f"{a.scene} | tersimpan: {saved} | SPASI simpan, Q keluar", (14, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("capture_photos", view)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            name = out / f"{a.scene}_{time.strftime('%Y%m%d_%H%M%S')}_{saved:03d}.jpg"
            cv2.imwrite(str(name), frame)
            saved += 1
            print("tersimpan:", name)
    cap.release()
    cv2.destroyAllWindows()
    print(f"Selesai: {saved} foto di {out}")


if __name__ == "__main__":
    main()
