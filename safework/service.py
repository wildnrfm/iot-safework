"""Lapisan layanan tanpa framework web. app.py (FastAPI) hanya membungkus fungsi-fungsi ini,
sehingga logikanya bisa diuji tanpa server dan mudah dipindah ke framework lain (mis. Next.js API)."""
from __future__ import annotations

import hmac
from typing import Iterator, Optional

from .indicators import Indicator
from .labels import APD_ITEMS, ITEM_NAMES_ID
from .profiles import ProfileStore
from .runner import Runner
from .storage import HistoryStore


class Service:
    def __init__(self, runner: Runner, profiles: ProfileStore, history: HistoryStore, indicator: Indicator,
                 mode: str = "nyata", admin_token: Optional[str] = None, retention_days: int = 30):
        self.runner = runner
        self.profiles = profiles
        self.history = history
        self.indicator = indicator
        self.mode = mode
        self.admin_token = admin_token
        self.retention_days = retention_days

    # ------------------------------------------------------------------ siklus hidup
    def start(self) -> None:
        if self.retention_days:
            self.history.purge_older_than(self.retention_days)
        self.runner.start()

    def request_stop(self) -> None:
        """Dipanggil saat Ctrl+C, sebelum server menunggu koneksi terbuka (stream video) ditutup."""
        self.runner.request_stop()

    def stop(self) -> None:
        self.runner.stop()
        self.indicator.close()
        self.history.close()

    # ------------------------------------------------------------------ data
    def state(self) -> dict:
        state = self.runner.state()
        state["mode"] = self.mode
        return state

    def profiles_payload(self) -> dict:
        return {
            "active": self.profiles.active_id,
            "profiles": [p.to_dict() for p in self.profiles.list()],
            "items": [{"item": i, "name": ITEM_NAMES_ID[i]} for i in APD_ITEMS],
        }

    def save_profile(self, payload: dict) -> dict:
        """Melempar ValueError bila payload tidak valid."""
        return self.profiles.upsert(payload).to_dict()

    def delete_profile(self, pid: str) -> None:
        """Melempar KeyError bila tidak ada, ValueError bila itu profil terakhir."""
        self.profiles.delete(pid)

    def set_active(self, pid: str) -> dict:
        """Melempar KeyError bila profil tidak ada."""
        return self.profiles.set_active(pid).to_dict()

    def history_list(self, limit: int = 50) -> list[dict]:
        rows = self.history.recent(max(1, min(int(limit), 500)))
        for row in rows:
            row["missing_names"] = [ITEM_NAMES_ID.get(i, i) for i in row["missing"]]
            row["uncertain_names"] = [ITEM_NAMES_ID.get(i, i) for i in row["uncertain"]]
        return rows

    def summary(self) -> dict:
        data = self.history.summary()
        for key in ("top_missing", "top_uncertain"):
            for row in data[key]:
                row["name"] = ITEM_NAMES_ID.get(row["item"], row["item"])
        return data

    def history_csv(self) -> str:
        return self.history.to_csv()

    def test_indicator(self) -> None:
        self.indicator.test()

    # ------------------------------------------------------------------ keamanan sederhana
    def is_admin(self, token: Optional[str]) -> bool:
        """Bila admin_token tidak diatur, semua perubahan diizinkan (cukup untuk demo lokal)."""
        if not self.admin_token:
            return True
        return token is not None and hmac.compare_digest(token, self.admin_token)

    # ------------------------------------------------------------------ video
    def mjpeg(self) -> Iterator[bytes]:
        last = 0
        while not self.runner.stopped:
            frame_id, jpeg = self.runner.wait_for_frame(last, timeout=1.0)
            if jpeg is None or frame_id == last:
                continue
            last = frame_id
            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode("ascii")
                   + b"\r\n\r\n" + jpeg + b"\r\n")
