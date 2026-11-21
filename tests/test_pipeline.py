import tempfile
import time
import unittest
from pathlib import Path

from safework.checkpoint import Checkpoint, CheckpointConfig
from safework.config import Settings
from safework.fakes import ScriptedDetector, SyntheticSource
from safework.indicators import MultiIndicator, VirtualIndicator
from safework.profiles import ProfileStore
from safework.runner import Runner, RunnerConfig
from safework.service import Service
from safework.storage import HistoryStore
from safework.app import create_app

from .helpers import wait_for


class CropDetector:
    """Detektor palsu yang mencatat ukuran gambar yang diterimanya."""
    supports_crop = True
    supported_labels = None

    def __init__(self):
        self.shapes = []

    def detect(self, frame):
        from safework.schemas import Detection
        self.shapes.append(tuple(frame.shape[:2]))
        return [Detection("person", 0.9, (10.0, 20.0, 50.0, 60.0))]


class ToggleSource:
    """Kamera palsu yang bisa 'dicabut'."""

    def __init__(self):
        self.ok = True
        self._inner = SyntheticSource(320, 180)

    def read(self):
        return self._inner.read() if self.ok else None

    def close(self):
        pass


def build(source, detector_factory, runner_cfg=None):
    tmp = tempfile.TemporaryDirectory()
    profiles = ProfileStore(Path(tmp.name) / "profiles.json")
    history = HistoryStore(":memory:")
    virtual = VirtualIndicator()
    indicator = MultiIndicator([virtual])
    cfg = CheckpointConfig(confirm_frames=2, check_seconds=0.6, min_check_seconds=0.2, hold_seconds=0.4,
                           absent_seconds=0.3)
    cp = Checkpoint(profiles.active(), cfg)
    runner = Runner(source, detector_factory(profiles), profiles, cp, indicator, history,
                    runner_cfg or RunnerConfig(target_fps=40, fault_after_seconds=0.3))
    service = Service(runner, profiles, history, indicator, mode="simulasi", admin_token="rahasia")
    return tmp, service, virtual


class PipelineTests(unittest.TestCase):
    def test_smoke_endpoint_fastapi(self):
        from fastapi.testclient import TestClient

        tmp, svc, _ = build(SyntheticSource(64, 64), lambda p: ScriptedDetector(p.active))
        self.addCleanup(tmp.cleanup)
        app = create_app(svc)

        with TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/api/state").status_code, 200)
            self.assertEqual(client.get("/api/history.csv").status_code, 200)
            self.assertEqual(client.post("/api/profiles/active", json={"id": "pekerja-proyek-desa"}).status_code, 401)
            allowed = client.post(
                "/api/profiles/active",
                json={"id": "pekerja-proyek-desa"},
                headers={"X-Admin-Token": "rahasia"},
            )
            self.assertEqual(allowed.status_code, 200)

    def test_simulasi_menghasilkan_riwayat_lampu_dan_video(self):
        tmp, svc, virtual = build(SyntheticSource(320, 180),
                                  lambda p: ScriptedDetector(p.active, present_seconds=1.5, gap_seconds=0.6))
        self.addCleanup(tmp.cleanup)
        svc.start()
        try:
            self.assertTrue(wait_for(lambda: len(svc.history.recent()) >= 2, timeout=10))
            rows = svc.history_list()
            state = svc.state()
            frame = next(svc.mjpeg())
            summary = svc.summary()
        finally:
            svc.stop()
        statuses = {r["status"] for r in rows}
        self.assertTrue({"lengkap", "belum_lengkap"} <= statuses, statuses)
        self.assertIn("headline", state)
        self.assertEqual(state["mode"], "simulasi")
        self.assertIn(state["indicator"]["lamp"], {"OFF", "GREEN", "YELLOW", "RED"})
        self.assertTrue(frame.startswith(b"--frame") and b"\xff\xd8" in frame)   # JPEG di dalam frame MJPEG
        self.assertGreaterEqual(summary["total"], 2)

    def test_kamera_dicabut_menjadi_gangguan_lalu_pulih(self):
        source = ToggleSource()
        tmp, svc, virtual = build(source, lambda p: ScriptedDetector(p.active, present_seconds=100, gap_seconds=1))
        self.addCleanup(tmp.cleanup)
        svc.start()
        try:
            source.ok = False
            self.assertTrue(wait_for(lambda: svc.state()["fault"] == "kamera_terputus", timeout=5))
            state = svc.state()
            self.assertFalse(state["camera_ok"])
            self.assertEqual(state["indicator"]["lamp"], "FAULT")
            self.assertEqual(state["headline"], "Kamera terputus")
            source.ok = True
            self.assertTrue(wait_for(lambda: svc.state()["fault"] == "", timeout=5))
            self.assertNotEqual(svc.state()["indicator"]["lamp"], "FAULT")
        finally:
            svc.stop()

    def test_ganti_profil_saat_berjalan(self):
        tmp, svc, virtual = build(SyntheticSource(320, 180),
                                  lambda p: ScriptedDetector(p.active, present_seconds=100, gap_seconds=1))
        self.addCleanup(tmp.cleanup)
        svc.start()
        try:
            svc.set_active("pekerja-proyek-desa")
            self.assertTrue(wait_for(lambda: svc.state()["profile"]["id"] == "pekerja-proyek-desa", timeout=5))
        finally:
            svc.stop()

    def test_request_stop_mengakhiri_stream_video_dengan_cepat(self):
        tmp, svc, virtual = build(SyntheticSource(320, 180),
                                  lambda p: ScriptedDetector(p.active, present_seconds=100, gap_seconds=1))
        self.addCleanup(tmp.cleanup)
        svc.start()
        try:
            stream = svc.mjpeg()
            self.assertTrue(next(stream).startswith(b"--frame"))
            started = time.monotonic()
            svc.request_stop()                                   # seperti Ctrl+C: koneksi stream harus selesai
            self.assertEqual(list(stream), [])                   # generator berakhir, tidak menggantung
            self.assertLess(time.monotonic() - started, 1.5)
        finally:
            svc.stop()

    def test_token_admin(self):
        tmp, svc, _ = build(SyntheticSource(64, 64), lambda p: ScriptedDetector(p.active))
        self.addCleanup(tmp.cleanup)
        self.assertFalse(svc.is_admin(None))
        self.assertFalse(svc.is_admin("salah"))
        self.assertTrue(svc.is_admin("rahasia"))
        svc.admin_token = None
        self.assertTrue(svc.is_admin(None))        # tanpa token: demo lokal diizinkan
        svc.history.close()

    def test_pengaturan_dari_argumen(self):
        s = Settings.from_args(["--fake", "--port", "9000", "--serial", "COM5"])
        self.assertTrue(s.fake)
        self.assertEqual((s.port, s.serial_port, s.host), (9000, "COM5", "127.0.0.1"))

    def test_simulasi_memakai_folder_data_sendiri_kecuali_ditentukan(self):
        self.assertEqual(Settings.from_args(["--fake"]).data_dir, "data_sim")
        self.assertEqual(Settings.from_args([]).data_dir, "data")
        self.assertEqual(Settings.from_args(["--fake", "--data-dir", "lain"]).data_dir, "lain")

    def test_overlay_bukti_tebal_dan_berwarna_deteksi_diabaikan_tipis_dan_abu(self):
        import numpy as np
        from safework.checkpoint import Snapshot
        from safework.render import GREEN, draw_overlay, encode_jpeg
        from safework.schemas import Detection, Phase
        snap = Snapshot(Phase.WAITING, None, (), 0.0, 0.0)
        det = Detection("helmet", 0.91, (200.0, 150.0, 300.0, 250.0))
        px = lambda f, x, y: tuple(int(v) for v in f[y, x])  # noqa: E731
        dipakai = np.zeros((360, 640, 3), dtype=np.uint8)
        draw_overlay(dipakai, [det], "Menunggu pekerja", snap, used=[det])
        self.assertEqual(px(dipakai, 205, 148), GREEN)          # latar label berwarna kelas
        self.assertEqual(px(dipakai, 201, 200), GREEN)          # garis tebal (3 piksel)
        diabaikan = np.zeros((360, 640, 3), dtype=np.uint8)
        draw_overlay(diabaikan, [det], "Menunggu pekerja", snap)
        self.assertEqual(px(diabaikan, 205, 148), (90, 90, 90))  # latar label abu-abu
        self.assertEqual(px(diabaikan, 201, 200), (0, 0, 0))     # garis tipis (1 piksel)
        self.assertTrue(encode_jpeg(dipakai).startswith(b"\xff\xd8"))

    def test_ambang_roi_dan_debug_dari_argumen(self):
        import contextlib
        import io
        s = Settings.from_args(["--conf-neg", "0.3", "--roi", "0.25,0,0.75,1", "--debug"])
        self.assertEqual((s.conf_neg, s.conf_pos, s.roi, s.debug), (0.3, 0.5, (0.25, 0.0, 0.75, 1.0), True))
        # PowerShell memecah "0.25,0,0.75,1" tanpa tanda kutip menjadi beberapa argumen: keduanya harus diterima
        tersebar = Settings.from_args(["--roi", "0.25", "0", "0.75", "1", "--debug"])
        self.assertEqual((tersebar.roi, tersebar.debug), ((0.25, 0.0, 0.75, 1.0), True))
        self.assertEqual(Settings.from_args([]).conf_neg, 0.35)
        self.assertIsNone(Settings.from_args([]).roi)
        self.assertTrue(Settings.from_args([]).roi_crop)
        self.assertFalse(Settings.from_args(["--no-roi-crop"]).roi_crop)
        for salah in ("0.8,0,0.2,1", "a,b,c,d", "0.1,0.1,0.9"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                Settings.from_args(["--roi", salah])

    def test_roi_memotong_frame_dan_mengembalikan_koordinat_ke_frame_penuh(self):
        import numpy as np
        det = CropDetector()
        tmp, svc, _ = build(SyntheticSource(64, 64), lambda p: det, runner_cfg=RunnerConfig(roi=(0.25, 0.0, 0.75, 1.0)))
        self.addCleanup(tmp.cleanup)
        found = svc.runner._detect(np.zeros((720, 1280, 3), dtype=np.uint8))
        self.assertEqual(det.shapes[-1], (720, 640))                      # hanya x 320..960 yang dikirim ke model
        self.assertEqual(found[0].box, (330.0, 20.0, 370.0, 60.0))        # digeser kembali ke ruang frame penuh
        svc.history.close()

    def test_tanpa_potong_bila_dimatikan_atau_detektor_tidak_mendukung(self):
        import numpy as np
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        det = CropDetector()
        tmp, svc, _ = build(SyntheticSource(64, 64), lambda p: det,
                            runner_cfg=RunnerConfig(roi=(0.25, 0.0, 0.75, 1.0), crop_to_roi=False))
        self.addCleanup(tmp.cleanup)
        svc.runner._detect(frame)
        self.assertEqual(det.shapes[-1], (720, 1280))                     # frame utuh
        svc.history.close()
        tmp2, svc2, _ = build(SyntheticSource(64, 64), lambda p: ScriptedDetector(p.active, present_seconds=100),
                              runner_cfg=RunnerConfig(roi=(0.25, 0.0, 0.75, 1.0)))
        self.addCleanup(tmp2.cleanup)
        orang = svc2.runner._detect(frame)[0]
        self.assertEqual(orang.box, (500.0, 40.0, 780.0, 700.0))          # koordinat mutlak tidak digeser
        svc2.history.close()

    def test_kotak_zona_debug_mengikuti_profil_aktif(self):
        tmp, svc, _ = build(SyntheticSource(64, 64), lambda p: ScriptedDetector(p.active))
        self.addCleanup(tmp.cleanup)
        zones = dict(svc.runner._zone_boxes((500.0, 40.0, 780.0, 700.0)))
        self.assertEqual(set(zones), {"mask", "gloves", "goggles", "boots"})   # profil bawaan Penyemprot
        x1, y1, x2, y2 = zones["goggles"]
        self.assertTrue(x1 < x2 and y1 < y2)
        svc.history.close()

    def test_mode_debug_dan_roi_tetap_menghasilkan_video(self):
        cfg = RunnerConfig(target_fps=40, roi=(0.0, 0.0, 1.0, 1.0), debug=True)
        tmp, svc, _ = build(SyntheticSource(1280, 720),
                            lambda p: ScriptedDetector(p.active, present_seconds=100, gap_seconds=1), runner_cfg=cfg)
        self.addCleanup(tmp.cleanup)
        svc.start()
        try:
            frame = next(svc.mjpeg())
        finally:
            svc.stop()
        self.assertTrue(frame.startswith(b"--frame") and b"\xff\xd8" in frame)


if __name__ == "__main__":
    unittest.main()
