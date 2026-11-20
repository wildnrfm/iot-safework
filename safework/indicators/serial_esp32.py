"""Indikator fisik: ESP32 lewat USB Serial.

Protokol (ASCII, satu perintah per baris, 115200 baud):
    laptop -> ESP32 : GREEN | YELLOW | RED | OFF | FAULT | TEST | PING
    ESP32 -> laptop : READY (saat boot) | OK | PONG | ERR
PING dikirim berkala sebagai heartbeat. Bila ESP32 tidak menerima apa pun beberapa detik,
ia masuk mode aman (kuning berkedip) agar lampu hijau lama tidak menyesatkan.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .base import Indicator, Lamp

log = logging.getLogger(__name__)


def _open_pyserial(port: str, baudrate: int):
    import serial  # pyserial; diimpor di sini agar mode simulasi tidak membutuhkannya

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baudrate
    ser.timeout = 0.1
    ser.write_timeout = 1.0
    ser.dtr = False   # cegah ESP32 ter-reset otomatis saat port dibuka
    ser.rts = False
    ser.open()
    return ser


def _safe_close(ser) -> None:
    try:
        ser.close()
    except Exception:  # noqa: BLE001
        pass


class SerialIndicator(Indicator):
    def __init__(self, port: str, baudrate: int = 115200, heartbeat_interval: float = 1.0,
                 reconnect_interval: float = 3.0, boot_delay: float = 2.0,
                 serial_factory: Optional[Callable] = None):
        self.port = port
        self.baudrate = baudrate
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_interval = reconnect_interval
        self.boot_delay = boot_delay
        self._factory = serial_factory or _open_pyserial
        self._lock = threading.RLock()
        self._ser = None
        self._lamp = Lamp.OFF
        self._last_ack = float("-inf")
        self._next_open = 0.0
        self._last_error = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="serial-indicator", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ API Indicator
    def set_lamp(self, lamp: Lamp) -> None:
        with self._lock:
            self._lamp = lamp
            if self._ser is not None:
                self._send(lamp.value)

    def test(self) -> None:
        with self._lock:
            if self._ser is not None:
                self._send("TEST")

    @property
    def connected(self) -> bool:
        with self._lock:
            limit = max(3.0, 3 * self.heartbeat_interval)
            return self._ser is not None and (time.monotonic() - self._last_ack) <= limit

    def info(self) -> dict:
        return {"serial": {"port": self.port, "connected": self.connected, "error": self._last_error}}

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        with self._lock:
            if self._ser is not None:
                self._send(Lamp.OFF.value)
                _safe_close(self._ser)
                self._ser = None

    # ------------------------------------------------------------------ internal
    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._ser is None:
                self._try_open()
            with self._lock:
                if self._ser is not None:
                    self._send("PING")
                    self._drain()
            self._stop.wait(self.heartbeat_interval)

    def _try_open(self) -> None:
        now = time.monotonic()
        if now < self._next_open:
            return
        try:
            ser = self._factory(self.port, self.baudrate)
        except Exception as exc:  # noqa: BLE001
            self._next_open = now + self.reconnect_interval
            self._last_error = str(exc)
            log.warning("Gagal membuka %s: %s", self.port, exc)
            return
        # Beri waktu board untuk boot bila sempat ter-reset saat port dibuka.
        if self.boot_delay > 0 and self._stop.wait(self.boot_delay):
            _safe_close(ser)
            return
        with self._lock:
            self._ser = ser
            self._last_error = ""
            self._last_ack = float("-inf")
            self._send(self._lamp.value)   # kirim ulang status terakhir setelah tersambung

    def _send(self, line: str) -> None:
        """Kirim satu perintah. Pemanggil harus memegang self._lock."""
        try:
            self._ser.write((line + "\n").encode("ascii"))
            self._ser.flush()
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def _drain(self) -> None:
        if self._ser is None:
            return
        try:
            waiting = self._ser.in_waiting
            if waiting:
                text = self._ser.read(waiting).decode("ascii", errors="ignore")
                if "PONG" in text or "OK" in text or "READY" in text:
                    self._last_ack = time.monotonic()
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def _fail(self, exc: Exception) -> None:
        log.warning("Koneksi serial %s terputus: %s", self.port, exc)
        if self._ser is not None:
            _safe_close(self._ser)
        self._ser = None
        self._last_error = str(exc)
        self._last_ack = float("-inf")
        self._next_open = time.monotonic() + self.reconnect_interval
