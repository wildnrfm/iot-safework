"""Pipeline utama: kamera -> deteksi -> evaluator -> pos cek -> indikator, riwayat, dan stream video."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .checkpoint import Checkpoint, Snapshot
from .evaluator import evaluate, filter_roi
from .labels import ZONES
from .indicators import Indicator, Lamp
from .messages import headline_detail
from .profiles import ProfileStore
from .schemas import Detection, FrameEvaluation, Phase, Requirement
from .storage import HistoryStore

log = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    target_fps: float = 10.0
    conf_person: float = 0.5
    conf_pos: float = 0.5
    conf_neg: float = 0.35                 # lebih rendah: recall kelas "tidak dipakai" model hanya ±0,3-0,65
    fault_after_seconds: float = 3.0       # tanpa gambar selama ini => gangguan kamera
    detect_errors_before_fault: int = 3
    jpeg_quality: int = 75
    draw_overlay: bool = True
    roi: Optional[tuple[float, float, float, float]] = None   # area pemeriksaan (pecahan 0-1): x1, y1, x2, y2
    debug: bool = False                    # gambar zona APD dan keterangan pada video
    crop_to_roi: bool = True               # hanya area ROI yang dikirim ke model (objek kecil jadi lebih besar)


class Runner:
    def __init__(self, source, detector, profiles: ProfileStore, checkpoint: Checkpoint, indicator: Indicator,
                 history: HistoryStore, cfg: Optional[RunnerConfig] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.source = source
        self.detector = detector
        self.profiles = profiles
        self.checkpoint = checkpoint
        self.indicator = indicator
        self.history = history
        self.cfg = cfg or RunnerConfig()
        self._clock = clock
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()
        self._state: dict = {}
        self._cond = threading.Condition()
        self._frame_id = 0
        self._jpeg: Optional[bytes] = None
        self._fault = ""
        self._last_frame_at = clock()
        self._phase_prev = Phase.WAITING
        self._detect_errors = 0
        self._fps = 0.0
        self._render_warned = False
        self._publish(self.checkpoint.snapshot(clock()), [], None)

    # ------------------------------------------------------------------ siklus hidup
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_frame_at = self._clock()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()

    def request_stop(self) -> None:
        """Beri sinyal berhenti tanpa menunggu: loop pipeline selesai dan stream video (MJPEG) berakhir."""
        self._stop.set()
        with self._cond:
            self._cond.notify_all()

    def stop(self) -> None:
        self.request_stop()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        close = getattr(self.source, "close", None)
        if close:
            close()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # ------------------------------------------------------------------ akses data
    def state(self) -> dict:
        with self._state_lock:
            state = dict(self._state)
        state["indicator"] = self.indicator.info()   # dibaca saat diminta agar status serial selalu segar
        return state

    def wait_for_frame(self, after_id: int, timeout: float = 1.0) -> tuple[int, Optional[bytes]]:
        with self._cond:
            if self._frame_id <= after_id and not self._stop.is_set():
                self._cond.wait(timeout)
            return self._frame_id, self._jpeg

    # ------------------------------------------------------------------ loop
    def _run(self) -> None:
        interval = 1.0 / max(self.cfg.target_fps, 0.1)
        while not self._stop.is_set():
            started = self._clock()
            try:
                self._step()
            except Exception:  # noqa: BLE001 - satu frame bermasalah tidak boleh mematikan pipeline
                log.exception("Kesalahan tak terduga pada pipeline")
            spent = self._clock() - started
            rate = 1.0 / max(spent, interval)
            self._fps = rate if self._fps == 0.0 else 0.9 * self._fps + 0.1 * rate
            self._stop.wait(max(0.0, interval - spent))

    def _step(self) -> None:
        now = self._clock()
        frame = self.source.read()
        if frame is None:
            self._on_no_frame(now)
            return
        self._last_frame_at = now
        if self._fault == "kamera_terputus":
            self._clear_fault(now)

        profile = self.profiles.active()
        if profile.id != self.checkpoint.profile.id:
            self.checkpoint.set_profile(profile)
            self.indicator.show_status(None)
            self._phase_prev = Phase.WAITING

        detections: list[Detection] = []
        try:
            detections = self._detect(frame)
            self._detect_errors = 0
            if self._fault == "deteksi_gagal":
                self._clear_fault(now)
        except Exception:  # noqa: BLE001
            log.exception("Deteksi gagal")
            self._detect_errors += 1
            if self._detect_errors >= self.cfg.detect_errors_before_fault and not self._fault:
                self._set_fault("deteksi_gagal", now)

        if self._fault:
            self._publish(self.checkpoint.snapshot(now), detections, frame)
            return

        height, width = frame.shape[:2]
        ev = evaluate(filter_roi(detections, self.cfg.roi, width, height), profile,
                      supported=getattr(self.detector, "supported_labels", None),
                      conf_person=self.cfg.conf_person, conf_pos=self.cfg.conf_pos, conf_neg=self.cfg.conf_neg)
        snap = self.checkpoint.update(ev, now)
        result = self.checkpoint.pop_finalized()
        if result is not None:
            self.history.add(result)
            self.indicator.show_status(result.status)
        elif self._phase_prev == Phase.RESULT and snap.phase != Phase.RESULT:
            self.indicator.show_status(None)
        self._phase_prev = snap.phase
        self._publish(snap, detections, frame, ev)

    def _detect(self, frame) -> list[Detection]:
        """Jalankan detektor. Bila ROI diberikan dan detektor mendukung, hanya area ROI yang diproses (dipotong):
        objek kecil seperti sarung tangan tampak lebih besar bagi model dan latar berantakan tidak ikut.
        Koordinat hasil dikembalikan ke ruang frame penuh."""
        roi = self.cfg.roi
        if roi is None or not self.cfg.crop_to_roi or not getattr(self.detector, "supports_crop", False):
            return self.detector.detect(frame)
        height, width = frame.shape[:2]
        x1, y1 = int(roi[0] * width), int(roi[1] * height)
        x2, y2 = int(roi[2] * width), int(roi[3] * height)
        if x2 - x1 < 32 or y2 - y1 < 32:
            return self.detector.detect(frame)
        found = self.detector.detect(frame[y1:y2, x1:x2].copy())
        return [Detection(d.label, d.conf, (d.box[0] + x1, d.box[1] + y1, d.box[2] + x1, d.box[3] + y1))
                for d in found]

    # ------------------------------------------------------------------ gangguan
    def _on_no_frame(self, now: float) -> None:
        if self._fault != "kamera_terputus" and now - self._last_frame_at >= self.cfg.fault_after_seconds:
            self._set_fault("kamera_terputus", now)
        self._publish(self.checkpoint.snapshot(now), [], None)

    def _set_fault(self, reason: str, now: float) -> None:
        log.warning("Gangguan: %s", reason)
        self._fault = reason
        self.checkpoint.set_fault(reason, now)
        self.indicator.set_lamp(Lamp.FAULT)
        self._phase_prev = Phase.FAULT

    def _clear_fault(self, now: float) -> None:
        log.info("Gangguan teratasi: %s", self._fault)
        self._fault = ""
        self.checkpoint.set_fault(None, now)
        self.indicator.show_status(None)
        self._phase_prev = Phase.WAITING

    # ------------------------------------------------------------------ publikasi
    def _publish(self, snap: Snapshot, detections: list[Detection], frame,
                 ev: Optional[FrameEvaluation] = None) -> None:
        headline, detail = headline_detail(snap)
        profile = self.checkpoint.profile
        state = {
            "ts": time.time(),
            "phase": snap.phase.value,
            "status": snap.status.value if snap.status else None,
            "headline": headline,
            "detail": detail,
            "profile": {"id": profile.id, "name": profile.name},
            "items": [i.to_dict() for i in snap.items],
            "hold_remaining": round(snap.hold_remaining, 1),
            "fps": round(self._fps, 1),
            "camera_ok": self._fault != "kamera_terputus",
            "fault": self._fault,
        }
        with self._state_lock:
            self._state = state
        if frame is not None:
            jpeg = self._render(frame, detections, headline, snap, ev)
            if jpeg is not None:
                with self._cond:
                    self._jpeg = jpeg
                    self._frame_id += 1
                    self._cond.notify_all()

    def _zone_boxes(self, subject_box) -> list:
        """Zona tubuh tiap APD pada profil aktif, dalam piksel, untuk mode --debug."""
        px1, py1, px2, py2 = subject_box
        w, h = px2 - px1, py2 - py1
        out = []
        for rule in self.checkpoint.profile.rules:
            if rule.requirement == Requirement.NOT_NEEDED:
                continue
            y_min, y_max, x_margin = ZONES[rule.item]
            out.append((rule.item, (int(px1 - x_margin * w), int(py1 + y_min * h),
                                    int(px2 + x_margin * w), int(py1 + y_max * h))))
        return out

    def _render(self, frame, detections: list[Detection], headline: str, snap: Snapshot,
                ev: Optional[FrameEvaluation] = None) -> Optional[bytes]:
        try:
            from .render import draw_overlay, encode_jpeg

            if self.cfg.draw_overlay:
                used = ev.used if ev else ()
                subject = ev.person_box if ev else None
                height, width = frame.shape[:2]
                roi_px = None
                if self.cfg.roi is not None:
                    r = self.cfg.roi
                    roi_px = (int(r[0] * width), int(r[1] * height), int(r[2] * width), int(r[3] * height))
                zones = self._zone_boxes(subject) if (self.cfg.debug and subject) else ()
                draw_overlay(frame, detections, headline, snap, used=used, subject_box=subject,
                             roi_px=roi_px, zones=zones, debug=self.cfg.debug)
            return encode_jpeg(frame, self.cfg.jpeg_quality)
        except Exception:  # noqa: BLE001
            if not self._render_warned:
                log.exception("Render frame gagal (stream video dimatikan; logika tetap berjalan)")
                self._render_warned = True
            return None
