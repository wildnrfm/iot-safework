import unittest

from safework.evaluator import evaluate, filter_roi, overall_status
from safework.fakes import PERSON_BOX, apd_box, scene
from safework.labels import canonical_label
from safework.profiles import default_profiles
from safework.schemas import Detection, ItemState, Status

from .helpers import make_profile

ALL4 = ["mask", "gloves", "goggles", "boots"]


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.sprayer = default_profiles()[0]  # masker, sarung tangan, kacamata, boots (semua wajib)

    def states(self, ev):
        return {i.item: i.state for i in ev.items}

    def test_semua_apd_terlihat_hasilnya_lengkap(self):
        ev = evaluate(scene(present=ALL4), self.sprayer)
        self.assertTrue(ev.person_found)
        self.assertTrue(all(s == ItemState.MET for s in self.states(ev).values()))
        self.assertEqual(overall_status(ev.items), Status.COMPLETE)

    def test_kelas_tidak_dipakai_adalah_bukti_pelanggaran(self):
        ev = evaluate(scene(present=["mask", "goggles", "boots"], absent=["gloves"]), self.sprayer)
        self.assertEqual(self.states(ev)["gloves"], ItemState.NOT_MET)
        self.assertEqual(overall_status(ev.items), Status.INCOMPLETE)

    def test_apd_tidak_terlihat_bukan_pelanggaran(self):
        ev = evaluate(scene(present=["mask", "gloves", "boots"]), self.sprayer)  # kacamata tidak terlihat
        self.assertEqual(self.states(ev)["goggles"], ItemState.UNCERTAIN)
        self.assertEqual(overall_status(ev.items), Status.UNCERTAIN)

    def test_bukti_bertentangan_dianggap_tidak_pasti(self):
        dets = scene(present=ALL4, absent=["gloves"])
        ev = evaluate(dets, self.sprayer)
        item = next(i for i in ev.items if i.item == "gloves")
        self.assertEqual((item.state, item.reason), (ItemState.UNCERTAIN, "bukti_bertentangan"))

    def test_pelanggaran_mengalahkan_ketidakpastian(self):
        ev = evaluate(scene(present=["mask", "boots"], absent=["gloves"]), self.sprayer)  # kacamata tak terlihat
        self.assertEqual(overall_status(ev.items), Status.INCOMPLETE)

    def test_tanpa_orang_atau_orang_berkeyakinan_rendah(self):
        self.assertFalse(evaluate([], self.sprayer).person_found)
        low = [Detection("person", 0.3, PERSON_BOX)]
        self.assertFalse(evaluate(low, self.sprayer).person_found)

    def test_opsional_dan_tidak_diperlukan_tidak_memengaruhi(self):
        profile = make_profile(("helmet", "wajib"), ("goggles", "opsional"), ("mask", "tidak_diperlukan"))
        ev = evaluate(scene(present=["helmet"], absent=["goggles"]), profile)
        self.assertEqual({i.item for i in ev.items}, {"helmet", "goggles"})  # masker tidak dievaluasi
        self.assertEqual(overall_status(ev.items), Status.COMPLETE)

    def test_kelas_tidak_didukung_model_tidak_pasti(self):
        ev = evaluate(scene(present=["helmet"]), make_profile(("helmet", "wajib"), ("gloves", "wajib")),
                      supported={"person", "helmet", "no_helmet"})
        item = next(i for i in ev.items if i.item == "gloves")
        self.assertEqual((item.state, item.reason), (ItemState.UNCERTAIN, "kelas_tidak_didukung"))

    def test_apd_di_luar_zona_tubuh_tidak_dihitung(self):
        x1, y1, x2, y2 = PERSON_BOX
        helm_di_kaki = Detection("helmet", 0.9, (x1 + 100, y2 - 60, x2 - 100, y2))
        ev = evaluate([Detection("person", 0.9, PERSON_BOX), helm_di_kaki], make_profile(("helmet", "wajib")))
        self.assertEqual(ev.items[0].state, ItemState.UNCERTAIN)

    def test_helm_milik_orang_lain_tidak_dihitung(self):
        orang_kecil = (50.0, 300.0, 150.0, 600.0)
        dets = scene(present=[]) + scene(present=["helmet"], person=orang_kecil)
        ev = evaluate(dets, make_profile(("helmet", "wajib")))  # subjek = orang terbesar, tanpa helm
        self.assertEqual(ev.person_box, PERSON_BOX)
        self.assertEqual(ev.items[0].state, ItemState.UNCERTAIN)

    def test_keyakinan_rendah_pada_apd_diabaikan(self):
        dets = [Detection("person", 0.9, PERSON_BOX), Detection("gloves", 0.3, apd_box("gloves"))]
        ev = evaluate(dets, make_profile(("gloves", "wajib")))
        self.assertEqual(ev.items[0].state, ItemState.UNCERTAIN)

    def test_bukti_yang_dipakai_dicatat_dan_yang_diabaikan_tidak(self):
        x1, y1, x2, y2 = PERSON_BOX
        dipakai = Detection("no_helmet", 0.60, apd_box("helmet"))                    # di zona kepala, keyakinan cukup
        rendah = Detection("no_helmet", 0.20, apd_box("helmet"))                     # di bawah ambang
        di_kaki = Detection("no_helmet", 0.90, (x1 + 90, y2 - 80, x2 - 90, y2))      # di luar zona kepala
        ev = evaluate([Detection("person", 0.9, PERSON_BOX), dipakai, rendah, di_kaki], make_profile(("helmet", "wajib")))
        self.assertEqual(ev.used, (dipakai,))
        self.assertEqual(ev.items[0].state, ItemState.NOT_MET)

    def test_ambang_tidak_dipakai_bawaan_lebih_longgar_dari_apd_terpasang(self):
        profil = make_profile(("gloves", "wajib"))
        orang = Detection("person", 0.9, PERSON_BOX)
        terpasang = [orang, Detection("gloves", 0.40, apd_box("gloves"))]
        tidak_dipakai = [orang, Detection("no_gloves", 0.40, apd_box("gloves"))]
        self.assertEqual(evaluate(terpasang, profil).items[0].state, ItemState.UNCERTAIN)       # perlu >= 0,5
        self.assertEqual(evaluate(tidak_dipakai, profil).items[0].state, ItemState.NOT_MET)     # cukup >= 0,35

    def test_roi_membuang_deteksi_di_luar_area_pemeriksaan(self):
        a = Detection("person", 0.9, (100, 100, 200, 200))      # pusat (150, 150)
        b = Detection("person", 0.9, (900, 100, 1000, 200))     # pusat (950, 150)
        self.assertEqual(filter_roi([a, b], None, 1280, 720), [a, b])
        self.assertEqual(filter_roi([a, b], (0.0, 0.0, 0.5, 1.0), 1280, 720), [a])
        self.assertEqual(filter_roi([a, b], (0.5, 0.0, 1.0, 1.0), 1280, 720), [b])

    def test_alias_nama_kelas_dataset(self):
        self.assertEqual(canonical_label("Safety Shoe"), "boots")
        self.assertEqual(canonical_label("Hardhat"), "helmet")
        self.assertEqual(canonical_label("no-goggle"), "no_goggle")
        self.assertEqual(canonical_label("Person"), "person")
        self.assertIsNone(canonical_label("none"))


if __name__ == "__main__":
    unittest.main()
