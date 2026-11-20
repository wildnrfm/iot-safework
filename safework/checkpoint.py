"""Mesin status pos cek: Menunggu -> Memeriksa -> Hasil -> Menunggu.

Konfirmasi per APD (asimetris, karena salah hijau jauh lebih berbahaya daripada salah merah):
  * TERPENUHI  : APD terlihat pada `confirm_frames` evaluasi BERTURUT-TURUT (ketat).
  * TIDAK TERPENUHI : bukti "tidak dipakai" muncul minimal `violation_votes` kali pada `window_frames` evaluasi
    terakhir DAN lebih banyak daripada bukti terpenuhi. Tidak perlu berturut-turut: recall kelas no_* model
    baseline hanya sekitar 0,55-0,65 per frame, jadi menuntut deteksi berturut-turut akan melewatkan banyak
    pelanggaran nyata (hasilnya kuning, bukan merah).
  * Selain itu TIDAK DAPAT DIPASTIKAN.
Semua waktu dikirim lewat argumen `now` (detik) sehingga mudah diuji tanpa menunggu waktu nyata.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from .evaluator import overall_status
from .schemas import (CheckResult, FrameEvaluation, ItemResult, ItemState, Phase, Profile, Requirement, Status)


@dataclass
class CheckpointConfig:
    confirm_frames: int = 4         # evaluasi berturut-turut "APD terlihat" sebelum satu APD dianggap terpenuhi
    violation_votes: int = 3        # bukti "tidak dipakai" yang dibutuhkan dalam jendela evaluasi terakhir
    window_frames: int = 10         # ukuran jendela evaluasi terakhir untuk pemungutan suara pelanggaran
    check_seconds: float = 3.0      # batas waktu memeriksa; setelahnya hasil diputuskan dari bukti yang ada
    min_check_seconds: float = 1.0  # hasil yang sudah pasti baru boleh keluar setelah memeriksa selama ini
    hold_seconds: float = 6.0       # lama hasil ditahan pada layar dan lampu
    absent_seconds: float = 1.5     # pekerja dianggap pergi bila tidak terlihat selama ini


@dataclass(frozen=True)
class Snapshot:
    phase: Phase
    status: Optional[Status]
    items: tuple[ItemResult, ...]
    since: float
    hold_remaining: float
    fault: str = ""


class Checkpoint:
    def __init__(self, profile: Profile, config: Optional[CheckpointConfig] = None):
        self.cfg = config or CheckpointConfig()
        self.profile = profile
        self.reset()

    # ------------------------------------------------------------------ kontrol
    def reset(self, profile: Optional[Profile] = None) -> None:
        if profile is not None:
            self.profile = profile
        self.phase = Phase.WAITING
        self.last_result: Optional[CheckResult] = None
        self._since = 0.0
        self._armed = True              # False setelah hasil LENGKAP, sampai pekerja pergi
        self._last_seen = float("-inf")
        self._check_started = 0.0
        self._frames = 0
        self._hist: dict[str, deque] = {}    # item -> (state, alasan) pada `window_frames` evaluasi terakhir
        self._met_run: dict[str, int] = {}   # item -> jumlah evaluasi "terpenuhi" berturut-turut sampai sekarang
        self._finalized: Optional[CheckResult] = None
        self._fault = ""

    def set_profile(self, profile: Profile) -> None:
        self.reset(profile)

    def set_fault(self, reason: Optional[str], now: float) -> None:
        """Tandai gangguan (mis. kamera terputus). reason=None mencabut gangguan."""
        if reason:
            if self.phase != Phase.FAULT:
                self.phase = Phase.FAULT
                self._since = now
                self._fault = reason
                self._clear_evidence()
        elif self.phase == Phase.FAULT:
            self.phase = Phase.WAITING
            self._since = now
            self._fault = ""
            self._armed = True
            self._last_seen = float("-inf")

    def pop_finalized(self) -> Optional[CheckResult]:
        result, self._finalized = self._finalized, None
        return result

    # ------------------------------------------------------------------ pembaruan per frame
    def update(self, ev: FrameEvaluation, now: float) -> Snapshot:
        if self.phase == Phase.FAULT:
            return self.snapshot(now)

        person = ev.person_found
        if person:
            self._last_seen = now
        absent_for = now - self._last_seen   # tak hingga bila belum pernah terlihat

        if self.phase == Phase.WAITING:
            if person and self._armed:
                self._start_check(now)
                self._accumulate(ev)
            elif not person and absent_for >= self.cfg.absent_seconds:
                self._armed = True

        elif self.phase == Phase.CHECKING:
            if not person:
                # Hasil hanya diputuskan saat pekerja masih terlihat. Bila ia pergi, batalkan pemeriksaan.
                if absent_for >= self.cfg.absent_seconds:
                    self._abort(now)
                return self.snapshot(now)
            self._accumulate(ev)
            elapsed = now - self._check_started
            decided = elapsed >= self.cfg.min_check_seconds and self._all_required_decided()
            if decided or elapsed >= self.cfg.check_seconds:
                self._finalize(now)

        elif self.phase == Phase.RESULT:
            if now - self._since >= self.cfg.hold_seconds:
                self._end_result(now, person)

        return self.snapshot(now)

    def snapshot(self, now: float) -> Snapshot:
        if self.phase == Phase.RESULT and self.last_result is not None:
            remaining = max(0.0, self.cfg.hold_seconds - (now - self._since))
            return Snapshot(self.phase, self.last_result.status, self.last_result.items, self._since, remaining)
        if self.phase == Phase.CHECKING:
            return Snapshot(self.phase, None, self._current_items(), self._since, 0.0)
        return Snapshot(self.phase, None, (), self._since, 0.0, self._fault)

    # ------------------------------------------------------------------ internal
    def _clear_evidence(self) -> None:
        self._frames = 0
        self._hist = {}
        self._met_run = {}

    def _start_check(self, now: float) -> None:
        self.phase = Phase.CHECKING
        self._since = now
        self._check_started = now
        self._clear_evidence()

    def _abort(self, now: float) -> None:
        self.phase = Phase.WAITING
        self._since = now
        self._clear_evidence()
        self._armed = True

    def _accumulate(self, ev: FrameEvaluation) -> None:
        self._frames += 1
        for it in ev.items:
            hist = self._hist.setdefault(it.item, deque(maxlen=max(1, self.cfg.window_frames)))
            hist.append((it.state, it.reason))
            self._met_run[it.item] = self._met_run.get(it.item, 0) + 1 if it.state == ItemState.MET else 0

    def _verdict(self, item: str) -> tuple[ItemState, str]:
        hist = self._hist.get(item)
        if not hist:
            return ItemState.UNCERTAIN, "belum_diperiksa"
        met = sum(1 for state, _ in hist if state == ItemState.MET)
        not_met = sum(1 for state, _ in hist if state == ItemState.NOT_MET)
        if not_met >= self.cfg.violation_votes and not_met > met:
            reason = next(r for state, r in reversed(hist) if state == ItemState.NOT_MET)
            return ItemState.NOT_MET, reason
        if self._met_run.get(item, 0) >= self.cfg.confirm_frames:
            return ItemState.MET, "terlihat"
        if len(hist) < self.cfg.confirm_frames:
            return ItemState.UNCERTAIN, "belum_stabil"
        return ItemState.UNCERTAIN, hist[-1][1]

    def _all_required_decided(self) -> bool:
        """Semua APD wajib sudah pasti (terpenuhi atau terbukti tidak dipakai)."""
        required = [r.item for r in self.profile.rules if r.requirement == Requirement.REQUIRED]
        return all(self._verdict(i)[0] != ItemState.UNCERTAIN for i in required)

    def _current_items(self) -> tuple[ItemResult, ...]:
        out = []
        for rule in self.profile.rules:
            if rule.requirement == Requirement.NOT_NEEDED:
                continue
            state, reason = self._verdict(rule.item)
            out.append(ItemResult(rule.item, rule.requirement, state, reason))
        return tuple(out)

    def _finalize(self, now: float) -> None:
        items = self._current_items()
        required = [i for i in items if i.requirement == Requirement.REQUIRED]
        result = CheckResult(
            status=overall_status(items),
            profile_id=self.profile.id,
            profile_name=self.profile.name,
            items=items,
            missing=tuple(i.item for i in required if i.state == ItemState.NOT_MET),
            uncertain=tuple(i.item for i in required if i.state == ItemState.UNCERTAIN),
            started_at=self._check_started,
            finished_at=now,
        )
        self.last_result = result
        self._finalized = result
        self.phase = Phase.RESULT
        self._since = now

    def _end_result(self, now: float, person: bool) -> None:
        # Hasil belum lengkap + pekerja masih di depan kamera: periksa ulang otomatis
        # (pekerja melengkapi APD lalu langsung dicek lagi).
        if person and self.last_result is not None and self.last_result.status != Status.COMPLETE:
            self._start_check(now)
            return
        # Hasil lengkap: tunggu sampai pekerja pergi sebelum memeriksa orang berikutnya.
        self.phase = Phase.WAITING
        self._since = now
        self._armed = False
