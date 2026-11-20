"""Riwayat pemeriksaan di SQLite lokal. Hanya hasil teks yang disimpan, bukan video."""
from __future__ import annotations

import csv
import io
import sqlite3
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from .schemas import CheckResult


def _split(text: str) -> list[str]:
    return [t for t in text.split(",") if t]


def _iso_local(epoch: float) -> str:
    """Waktu lokal ISO-8601 dari epoch. Dihitung dari UTC + selisih zona saat ini, bukan lewat localtime(),
    karena localtime() di Windows gagal (OSError) untuk epoch yang kecil."""
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(timezone(offset)).isoformat(timespec="seconds")


class HistoryStore:
    def __init__(self, path: str = ":memory:"):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS checks (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts_epoch REAL NOT NULL,
                   ts TEXT NOT NULL,
                   profile_id TEXT NOT NULL,
                   profile_name TEXT NOT NULL,
                   status TEXT NOT NULL,
                   missing TEXT NOT NULL DEFAULT '',
                   uncertain TEXT NOT NULL DEFAULT '',
                   duration_ms INTEGER NOT NULL DEFAULT 0)"""
        )
        self._db.commit()

    def add(self, result: CheckResult, epoch: Optional[float] = None) -> int:
        epoch = time.time() if epoch is None else epoch
        stamp = _iso_local(epoch)
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO checks (ts_epoch, ts, profile_id, profile_name, status, missing, uncertain, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (epoch, stamp, result.profile_id, result.profile_name, result.status.value,
                 ",".join(result.missing), ",".join(result.uncertain), int(result.duration * 1000)),
            )
            self._db.commit()
            return int(cur.lastrowid)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "ts": row["ts"], "ts_epoch": row["ts_epoch"],
            "profile_id": row["profile_id"], "profile_name": row["profile_name"],
            "status": row["status"], "missing": _split(row["missing"]), "uncertain": _split(row["uncertain"]),
            "duration_ms": row["duration_ms"],
        }

    def recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM checks ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._row(r) for r in rows]

    def summary(self, first_try_gap: float = 45.0, max_rows: int = 5000) -> dict:
        """Ringkasan untuk evaluasi bersama. "Percobaan pertama" = pemeriksaan yang tidak didahului
        pemeriksaan lain dalam `first_try_gap` detik (pekerja yang sama mengulang setelah melengkapi APD)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM checks ORDER BY id DESC LIMIT ?) ORDER BY id ASC", (int(max_rows),)
            ).fetchall()
        by_status: Counter = Counter()
        missing: Counter = Counter()
        uncertain: Counter = Counter()
        first_total = first_ok = 0
        prev: Optional[float] = None
        for r in rows:
            by_status[r["status"]] += 1
            missing.update(_split(r["missing"]))
            uncertain.update(_split(r["uncertain"]))
            if prev is None or r["ts_epoch"] - prev > first_try_gap:
                first_total += 1
                first_ok += 1 if r["status"] == "lengkap" else 0
            prev = r["ts_epoch"]
        return {
            "total": len(rows),
            "by_status": dict(by_status),
            "top_missing": [{"item": k, "count": v} for k, v in missing.most_common(5)],
            "top_uncertain": [{"item": k, "count": v} for k, v in uncertain.most_common(5)],
            "first_try_total": first_total,
            "first_try_complete_rate": (first_ok / first_total) if first_total else None,
        }

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "waktu", "profil", "hasil", "apd_kurang", "apd_tidak_pasti", "durasi_ms"])
        with self._lock:
            rows = self._db.execute("SELECT * FROM checks ORDER BY id ASC").fetchall()
        for r in rows:
            writer.writerow([r["id"], r["ts"], r["profile_name"], r["status"], r["missing"], r["uncertain"],
                             r["duration_ms"]])
        return buf.getvalue()

    def purge_older_than(self, days: float) -> int:
        """Hapus riwayat lama (masa simpan data). Mengembalikan jumlah baris yang dihapus."""
        cutoff = time.time() - days * 86400
        with self._lock:
            cur = self._db.execute("DELETE FROM checks WHERE ts_epoch < ?", (cutoff,))
            self._db.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._db.close()
