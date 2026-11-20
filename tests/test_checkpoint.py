import unittest

from safework.checkpoint import Checkpoint, CheckpointConfig
from safework.fakes import scene
from safework.schemas import Phase, Status

from .helpers import Driver, make_profile

PROFIL = make_profile(("helmet", "wajib"), ("gloves", "wajib"))
LENGKAP = scene(present=["helmet", "gloves"])
TANPA_SARUNG = scene(present=["helmet"], absent=["gloves"])
SARUNG_TAK_TERLIHAT = scene(present=["helmet"])


def driver(**cfg):
    config = CheckpointConfig(confirm_frames=3, check_seconds=3.0, min_check_seconds=1.0,
                              hold_seconds=6.0, absent_seconds=1.5)
    for k, v in cfg.items():
        setattr(config, k, v)
    return Driver(Checkpoint(PROFIL, config))


class CheckpointTests(unittest.TestCase):
    def test_hasil_pasti_menunggu_waktu_pemeriksaan_minimum(self):
        d = driver()
        snap = d.feed(LENGKAP, 0.6)
        self.assertEqual(snap.phase, Phase.CHECKING)
        self.assertEqual(d.results, [])
        snap = d.feed(LENGKAP, 0.8)
        self.assertEqual(snap.phase, Phase.RESULT)
        self.assertEqual([r.status for r in d.results], [Status.COMPLETE])

    def test_pelanggaran_terbukti_keluar_merah_dengan_daftar_apd(self):
        d = driver()
        d.feed(TANPA_SARUNG, 1.5)
        self.assertEqual(len(d.results), 1)
        self.assertEqual(d.results[0].status, Status.INCOMPLETE)
        self.assertEqual(d.results[0].missing, ("gloves",))

    def test_apd_tidak_terlihat_menunggu_batas_waktu_lalu_kuning(self):
        d = driver()
        snap = d.feed(SARUNG_TAK_TERLIHAT, 2.0)
        self.assertEqual(snap.phase, Phase.CHECKING)       # masih mencari bukti
        snap = d.feed(SARUNG_TAK_TERLIHAT, 1.4)
        self.assertEqual(snap.phase, Phase.RESULT)
        self.assertEqual(d.results[0].status, Status.UNCERTAIN)
        self.assertEqual(d.results[0].uncertain, ("gloves",))

    def test_deteksi_berkedip_tidak_pernah_menjadi_hijau(self):
        d = driver()
        for _ in range(20):                                 # sarung tangan muncul-hilang tiap frame
            d.feed(LENGKAP, 0.1)
            d.feed(SARUNG_TAK_TERLIHAT, 0.1)
        self.assertEqual(d.results[0].status, Status.UNCERTAIN)

    def test_pelanggaran_yang_terdeteksi_putus_putus_tetap_merah(self):
        # recall kelas no_* hanya ±60% per frame: bukti muncul tidak berturut-turut (tak pernah 3 berturut-turut)
        d = driver()
        pola = [TANPA_SARUNG, SARUNG_TAK_TERLIHAT, TANPA_SARUNG, TANPA_SARUNG, SARUNG_TAK_TERLIHAT,
                TANPA_SARUNG, SARUNG_TAK_TERLIHAT, TANPA_SARUNG, TANPA_SARUNG, SARUNG_TAK_TERLIHAT]
        d.feed_frames(pola * 3)
        self.assertEqual(d.results[0].status, Status.INCOMPLETE)
        self.assertEqual(d.results[0].missing, ("gloves",))

    def test_satu_dua_deteksi_palsu_tidak_membuat_merah(self):
        d = driver()
        palsu = TANPA_SARUNG                                     # sarung tangan salah dibaca "tidak dipakai"
        d.feed_frames([LENGKAP] * 3 + [palsu] + [LENGKAP] * 4 + [palsu] + [LENGKAP] * 8)
        self.assertEqual(d.results[0].status, Status.COMPLETE)

    def test_bukti_terpenuhi_yang_dominan_mengalahkan_deteksi_palsu_berulang(self):
        d = driver()
        palsu = TANPA_SARUNG
        d.feed_frames([LENGKAP, LENGKAP, palsu, LENGKAP, LENGKAP, palsu, LENGKAP, LENGKAP, palsu,
                       LENGKAP, LENGKAP, LENGKAP, LENGKAP, LENGKAP])   # 3 suara palsu, tetapi 11 bukti terpenuhi
        self.assertEqual(d.results[0].status, Status.COMPLETE)

    def test_pelanggaran_yang_tidak_cukup_suara_menjadi_kuning_bukan_merah(self):
        d = driver()
        d.feed_frames([TANPA_SARUNG, TANPA_SARUNG] + [SARUNG_TAK_TERLIHAT] * 40)   # hanya 2 suara pelanggaran
        self.assertEqual(d.results[0].status, Status.UNCERTAIN)

    def test_pekerja_pergi_saat_diperiksa_tidak_menghasilkan_hasil(self):
        d = driver()
        d.feed(LENGKAP, 0.5)
        snap = d.feed([], 2.0)
        self.assertEqual(snap.phase, Phase.WAITING)
        self.assertEqual(d.results, [])

    def test_hasil_belum_lengkap_diperiksa_ulang_otomatis_selama_pekerja_masih_ada(self):
        d = driver()
        d.feed(TANPA_SARUNG, 1.5)                           # hasil merah
        snap = d.feed(TANPA_SARUNG, 5.0)                    # masih ditahan (hold 6 dtk)
        self.assertEqual(snap.phase, Phase.RESULT)
        snap = d.feed(LENGKAP, 1.0)                         # hold habis -> periksa ulang; APD sudah dilengkapi
        self.assertEqual(snap.phase, Phase.CHECKING)
        d.feed(LENGKAP, 1.5)
        self.assertEqual([r.status for r in d.results], [Status.INCOMPLETE, Status.COMPLETE])

    def test_setelah_lengkap_pekerja_harus_pergi_sebelum_pemeriksaan_berikutnya(self):
        d = driver()
        d.feed(LENGKAP, 1.5)
        d.feed(LENGKAP, 20.0)                               # berdiri terus di depan kamera
        self.assertEqual(len(d.results), 1)
        d.feed([], 2.0)                                     # pergi
        d.feed(LENGKAP, 2.0)                                # pekerja berikutnya
        self.assertEqual(len(d.results), 2)

    def test_ganti_profil_mengatur_ulang(self):
        d = driver()
        d.feed(LENGKAP, 0.5)
        d.cp.set_profile(make_profile(("boots", "wajib"), pid="lain"))
        self.assertEqual(d.cp.phase, Phase.WAITING)

    def test_gangguan_menghentikan_pemeriksaan_dan_pulih(self):
        d = driver()
        d.feed(LENGKAP, 0.5)
        d.cp.set_fault("kamera_terputus", d.t)
        snap = d.feed(LENGKAP, 2.0)
        self.assertEqual((snap.phase, snap.fault), (Phase.FAULT, "kamera_terputus"))
        self.assertEqual(d.results, [])
        d.cp.set_fault(None, d.t)
        self.assertEqual(d.cp.phase, Phase.WAITING)

    def test_sisa_waktu_tahan_berkurang(self):
        d = driver()
        d.feed(TANPA_SARUNG, 1.5)
        sisa_awal = d.cp.snapshot(d.t).hold_remaining
        sisa_akhir = d.feed(TANPA_SARUNG, 2.0).hold_remaining
        self.assertLess(sisa_akhir, sisa_awal)

    def test_profil_tanpa_apd_wajib_langsung_lengkap(self):
        cp = Checkpoint(make_profile(("goggles", "opsional")), CheckpointConfig(min_check_seconds=0.5))
        d = Driver(cp)
        d.feed(scene(present=[]), 1.0)
        self.assertEqual(d.results[0].status, Status.COMPLETE)


if __name__ == "__main__":
    unittest.main()
