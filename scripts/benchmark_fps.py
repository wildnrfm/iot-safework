"""Ukur kecepatan inferensi YOLO di laptopmu memakai webcam.

    python scripts/benchmark_fps.py --weights yolo11n.pt --frames 100
    python scripts/benchmark_fps.py --weights runs/ppe-v1/weights/best.pt --imgsz 480 --show

Pos cek tidak butuh FPS tinggi karena pekerjanya diam: sekitar 5 FPS sudah cukup.
Bila lambat, kecilkan --imgsz atau resolusi kamera, atau proses tiap 2-3 frame.
"""
import argparse
import statistics
import time


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolo11n.pt")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--show", action="store_true", help="tampilkan jendela hasil (tekan q untuk berhenti)")
    a = ap.parse_args()

    import cv2
    from ultralytics import YOLO

    model = YOLO(a.weights)
    print("Kelas model:", ", ".join(str(n) for n in model.names.values()))

    cap = cv2.VideoCapture(a.camera)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    if not cap.isOpened():
        raise SystemExit("Kamera tidak bisa dibuka. Coba --camera 1 atau periksa izin kamera.")

    times = []
    for i in range(a.frames + 5):                      # 5 frame pertama = pemanasan, tidak dihitung
        ok, frame = cap.read()
        if not ok:
            print("Gagal membaca frame, berhenti.")
            break
        start = time.perf_counter()
        result = model.predict(frame, imgsz=a.imgsz, verbose=False)[0]
        elapsed = time.perf_counter() - start
        if i >= 5:
            times.append(elapsed)
        if a.show:
            cv2.imshow("benchmark (q = berhenti)", result.plot())
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cap.release()
    cv2.destroyAllWindows()

    if not times:
        raise SystemExit("Tidak ada data waktu.")
    times.sort()
    mean = statistics.mean(times)
    p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
    print(f"\n{len(times)} frame | rata-rata {mean * 1000:.0f} ms ({1 / mean:.1f} FPS) | "
          f"median {statistics.median(times) * 1000:.0f} ms | p95 {p95 * 1000:.0f} ms")


if __name__ == "__main__":
    main()
