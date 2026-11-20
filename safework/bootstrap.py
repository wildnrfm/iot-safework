"""Rangkai komponen menjadi satu Service sesuai pengaturan."""
from __future__ import annotations

import logging
from pathlib import Path

from .checkpoint import Checkpoint, CheckpointConfig
from .config import Settings
from .indicators import Indicator, MultiIndicator, SerialIndicator, VirtualIndicator
from .profiles import ProfileStore
from .runner import Runner, RunnerConfig
from .service import Service
from .storage import HistoryStore

log = logging.getLogger(__name__)


def build_service(s: Settings) -> Service:
    data = Path(s.data_dir)
    data.mkdir(parents=True, exist_ok=True)
    profiles = ProfileStore(data / "profiles.json")
    history = HistoryStore(data / "history.db")

    # Indikator virtual selalu aktif (dashboard); ESP32 ditambahkan bila port serial diberikan.
    indicators: list[Indicator] = [VirtualIndicator()]
    if s.serial_port:
        indicators.append(SerialIndicator(s.serial_port))
        log.info("Indikator ESP32 di %s", s.serial_port)
    indicator = MultiIndicator(indicators)

    if s.fake:
        from .fakes import ScriptedDetector, SyntheticSource

        source = SyntheticSource()
        detector = ScriptedDetector(profiles.active)
    else:
        from .detectors import YoloDetector
        from .sources import Camera

        source = Camera(s.camera_index, s.camera_width, s.camera_height, s.camera_backend)
        detector = YoloDetector(s.weights, conf=s.conf)

    checkpoint = Checkpoint(profiles.active(), CheckpointConfig(
        confirm_frames=s.confirm_frames, violation_votes=s.violation_votes, window_frames=s.window_frames,
        check_seconds=s.check_seconds, min_check_seconds=s.min_check_seconds,
        hold_seconds=s.hold_seconds, absent_seconds=s.absent_seconds))
    runner = Runner(source, detector, profiles, checkpoint, indicator, history, RunnerConfig(
        target_fps=s.target_fps, conf_person=s.conf_person, conf_pos=s.conf_pos, conf_neg=s.conf_neg,
        roi=s.roi, debug=s.debug, crop_to_roi=s.roi_crop))
    return Service(runner, profiles, history, indicator, mode="simulasi" if s.fake else "nyata",
                   admin_token=s.admin_token, retention_days=s.retention_days)
