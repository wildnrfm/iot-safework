"""Detektor objek: pembungkus YOLO (Ultralytics) dengan pemetaan nama kelas ke label kanonis."""
from __future__ import annotations

from .labels import canonical_label
from .schemas import Detection


class YoloDetector:
    """Memuat bobot YOLO dan mengubah hasilnya menjadi daftar `Detection` berlabel kanonis.

    Kelas yang tidak dikenal (mis. "none") diabaikan. `supported_labels` dipakai evaluator untuk
    membedakan "APD tidak terlihat" dari "model memang tidak punya kelas ini".
    """

    supports_crop = True   # hasilnya hanya bergantung pada gambar, jadi boleh diberi potongan frame (ROI)

    def __init__(self, weights: str, conf: float = 0.25, imgsz: int = 640, device=None):
        from ultralytics import YOLO  # diimpor di sini agar mode simulasi tidak membutuhkannya

        self.model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz
        self.device = device
        self._class_map = {int(cid): canonical_label(name) for cid, name in self.model.names.items()}
        self.supported_labels = {label for label in self._class_map.values() if label}

    def detect(self, frame) -> list[Detection]:
        result = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz, device=self.device, verbose=False)[0]
        detections: list[Detection] = []
        for box in result.boxes:
            label = self._class_map.get(int(box.cls[0]))
            if label is None:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            detections.append(Detection(label, float(box.conf[0]), (x1, y1, x2, y2)))
        return detections
