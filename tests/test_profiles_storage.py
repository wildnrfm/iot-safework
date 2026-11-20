import tempfile
import unittest
from pathlib import Path

from safework.profiles import ProfileStore, parse_profile
from safework.schemas import Requirement, Status
from safework.storage import HistoryStore

from .helpers import make_result


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "profiles.json"

    def test_profil_bawaan_dibuat_saat_pertama_kali(self):
        store = ProfileStore(self.path)
        self.assertEqual([p.id for p in store.list()], ["penyemprot-pestisida", "pekerja-proyek-desa"])
        self.assertEqual(store.active_id, "penyemprot-pestisida")
        self.assertTrue(self.path.exists())

    def test_perubahan_tersimpan_dan_dimuat_ulang(self):
        store = ProfileStore(self.path)
        store.upsert({"id": "bengkel", "name": "Bengkel", "rules": [{"item": "goggles", "requirement": "wajib"}]})
        store.set_active("bengkel")
        lagi = ProfileStore(self.path)
        self.assertEqual(lagi.active().name, "Bengkel")
        self.assertEqual(lagi.get("bengkel").rules[0].requirement, Requirement.REQUIRED)

    def test_validasi(self):
        for bad in [
            {"id": "Salah ID", "name": "x", "rules": []},
            {"id": "ok", "name": "", "rules": []},
            {"id": "ok", "name": "x", "rules": [{"item": "topi-ajaib", "requirement": "wajib"}]},
            {"id": "ok", "name": "x", "rules": [{"item": "helmet", "requirement": "mungkin"}]},
            {"id": "ok", "name": "x", "rules": [{"item": "helmet"}, {"item": "helmet"}]},
        ]:
            with self.assertRaises(ValueError):
                parse_profile(bad)

    def test_hapus_profil_aktif_memindahkan_aktif_dan_profil_terakhir_tidak_boleh_dihapus(self):
        store = ProfileStore(self.path)
        store.delete("penyemprot-pestisida")
        self.assertEqual(store.active_id, "pekerja-proyek-desa")
        with self.assertRaises(ValueError):
            store.delete("pekerja-proyek-desa")
        with self.assertRaises(KeyError):
            store.delete("tidak-ada")

    def test_berkas_rusak_kembali_ke_profil_bawaan(self):
        self.path.write_text("{bukan json", encoding="utf-8")
        self.assertEqual(len(ProfileStore(self.path).list()), 2)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.db = HistoryStore(":memory:")
        self.addCleanup(self.db.close)

    def test_tambah_dan_baca_terbaru(self):
        self.db.add(make_result(Status.COMPLETE), epoch=1000)
        self.db.add(make_result(Status.INCOMPLETE, missing=["gloves"]), epoch=2000)
        rows = self.db.recent(10)
        self.assertEqual([r["status"] for r in rows], ["belum_lengkap", "lengkap"])
        self.assertEqual(rows[0]["missing"], ["gloves"])

    def test_ringkasan_dan_percobaan_pertama(self):
        # Pekerja A: merah lalu hijau (percobaan pertama gagal). Pekerja B (jauh kemudian): hijau.
        self.db.add(make_result(Status.INCOMPLETE, missing=["gloves"]), epoch=1000)
        self.db.add(make_result(Status.COMPLETE), epoch=1010)
        self.db.add(make_result(Status.COMPLETE), epoch=2000)
        s = self.db.summary(first_try_gap=45)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_status"], {"belum_lengkap": 1, "lengkap": 2})
        self.assertEqual(s["first_try_total"], 2)
        self.assertAlmostEqual(s["first_try_complete_rate"], 0.5)
        self.assertEqual(s["top_missing"], [{"item": "gloves", "count": 1}])

    def test_stempel_waktu_tidak_bergantung_pada_localtime_platform(self):
        from datetime import datetime
        from safework.storage import _iso_local
        import time
        for epoch in (0, 1000, 1_700_000_000, int(time.time())):
            self.assertEqual(int(datetime.fromisoformat(_iso_local(epoch)).timestamp()), epoch)

    def test_ringkasan_kosong(self):
        s = self.db.summary()
        self.assertEqual((s["total"], s["first_try_complete_rate"]), (0, None))

    def test_csv(self):
        self.db.add(make_result(Status.UNCERTAIN, uncertain=["goggles"], name="Penyemprot"), epoch=1000)
        lines = self.db.to_csv().strip().splitlines()
        self.assertEqual(lines[0], "id,waktu,profil,hasil,apd_kurang,apd_tidak_pasti,durasi_ms")
        self.assertIn("Penyemprot,tidak_dapat_dipastikan,,goggles", lines[1])

    def test_hapus_riwayat_lama(self):
        import time
        self.db.add(make_result(), epoch=time.time() - 40 * 86400)
        self.db.add(make_result(), epoch=time.time())
        self.assertEqual(self.db.purge_older_than(30), 1)
        self.assertEqual(len(self.db.recent()), 1)


if __name__ == "__main__":
    unittest.main()
