import threading
import unittest

from safework.indicators import Indicator, Lamp, MultiIndicator, SerialIndicator, VirtualIndicator
from safework.schemas import Status

from .helpers import wait_for


class FakeSerial:
    """Pengganti pyserial: mencatat tulisan dan membalas PONG/OK seperti firmware."""

    def __init__(self):
        self.writes = []
        self._rx = bytearray()
        self.closed = False
        self.fail_writes = False
        self._lock = threading.Lock()

    def write(self, data):
        if self.fail_writes:
            raise OSError("kabel dicabut")
        line = data.decode("ascii").strip()
        with self._lock:
            self.writes.append(line)
            self._rx += b"PONG\n" if line == "PING" else b"OK\n"

    def flush(self):
        pass

    @property
    def in_waiting(self):
        with self._lock:
            return len(self._rx)

    def read(self, n):
        with self._lock:
            out, self._rx = bytes(self._rx[:n]), self._rx[n:]
            return out

    def close(self):
        self.closed = True


class MappingTests(unittest.TestCase):
    def test_status_ke_lampu(self):
        v = VirtualIndicator()
        for status, lamp in [(Status.COMPLETE, "GREEN"), (Status.UNCERTAIN, "YELLOW"),
                             (Status.INCOMPLETE, "RED"), (None, "OFF")]:
            v.show_status(status)
            self.assertEqual(v.info()["lamp"], lamp)

    def test_beep_hanya_saat_pindah_ke_merah(self):
        v = VirtualIndicator()
        v.set_lamp(Lamp.RED)
        v.set_lamp(Lamp.RED)
        self.assertEqual(v.info()["beep_seq"], 1)
        v.set_lamp(Lamp.OFF)
        v.set_lamp(Lamp.RED)
        self.assertEqual(v.info()["beep_seq"], 2)

    def test_uji_menaikkan_penghitung_uji(self):
        v = VirtualIndicator()
        v.test()
        self.assertEqual(v.info()["test_seq"], 1)

    def test_kegagalan_satu_indikator_tidak_mengganggu_yang_lain(self):
        class Rusak(Indicator):
            def set_lamp(self, lamp):
                raise RuntimeError("rusak")

        v = VirtualIndicator()
        multi = MultiIndicator([Rusak(), v])
        multi.show_status(Status.COMPLETE)
        self.assertEqual(v.info()["lamp"], "GREEN")


class SerialIndicatorTests(unittest.TestCase):
    def make(self, fail_first=0):
        self.ports = []
        attempts = {"n": 0}

        def factory(port, baud):
            attempts["n"] += 1
            if attempts["n"] <= fail_first:
                raise OSError("port belum ada")
            fake = FakeSerial()
            self.ports.append(fake)
            return fake

        ind = SerialIndicator("COM_UJI", heartbeat_interval=0.02, reconnect_interval=0.05, boot_delay=0,
                              serial_factory=factory)
        self.addCleanup(ind.close)
        return ind

    def test_perintah_lampu_terkirim_dan_heartbeat_berjalan(self):
        ind = self.make()
        self.assertTrue(wait_for(lambda: ind.connected))
        ind.set_lamp(Lamp.RED)
        self.assertTrue(wait_for(lambda: "RED" in self.ports[0].writes))
        self.assertTrue(wait_for(lambda: self.ports[0].writes.count("PING") >= 3))

    def test_status_terakhir_dikirim_ulang_setelah_tersambung_kembali(self):
        ind = self.make()
        self.assertTrue(wait_for(lambda: ind.connected))
        ind.set_lamp(Lamp.RED)
        self.assertTrue(wait_for(lambda: "RED" in self.ports[0].writes))
        self.ports[0].fail_writes = True                    # kabel dicabut
        self.assertTrue(wait_for(lambda: len(self.ports) >= 2))
        self.assertTrue(wait_for(lambda: self.ports[1].writes[:1] == ["RED"]))
        self.assertTrue(self.ports[0].closed)

    def test_port_belum_ada_dicoba_lagi_sampai_tersambung(self):
        ind = self.make(fail_first=2)
        self.assertTrue(wait_for(lambda: ind.connected, timeout=3.0))
        self.assertEqual(ind.info()["serial"]["error"], "")

    def test_perintah_disimpan_selama_belum_tersambung(self):
        ind = self.make(fail_first=1)
        ind.set_lamp(Lamp.YELLOW)                           # dikirim begitu port terbuka
        self.assertTrue(wait_for(lambda: self.ports and self.ports[0].writes[:1] == ["YELLOW"]))

    def test_tutup_mengirim_off(self):
        ind = self.make()
        self.assertTrue(wait_for(lambda: ind.connected))
        ind.close()
        self.assertEqual(self.ports[0].writes[-1], "OFF")
        self.assertTrue(self.ports[0].closed)


if __name__ == "__main__":
    unittest.main()
