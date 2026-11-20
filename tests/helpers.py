"""Alat bantu pengujian."""
import time

from safework.evaluator import evaluate
from safework.schemas import CheckResult, Profile, PpeRule, Requirement, Status


def make_profile(*rules, pid="uji", name="Profil uji"):
    """make_profile(("helmet", "wajib"), ("goggles", "opsional"))"""
    return Profile(id=pid, name=name, rules=[PpeRule(i, Requirement(r)) for i, r in rules])


def make_result(status=Status.COMPLETE, missing=(), uncertain=(), pid="uji", name="Profil uji", duration=1.0):
    return CheckResult(status=status, profile_id=pid, profile_name=name, items=(), missing=tuple(missing),
                       uncertain=tuple(uncertain), started_at=0.0, finished_at=duration)


class Driver:
    """Mengumpan Checkpoint dengan deteksi pada waktu simulasi (tanpa menunggu waktu nyata)."""

    def __init__(self, checkpoint, step=0.1):
        self.cp = checkpoint
        self.step = step
        self.t = 0.0
        self.results = []

    def feed(self, detections, seconds):
        for _ in range(round(seconds / self.step)):
            ev = evaluate(detections, self.cp.profile)
            self.cp.update(ev, self.t)
            result = self.cp.pop_finalized()
            if result is not None:
                self.results.append(result)
            self.t += self.step
        return self.cp.snapshot(self.t)


def _feed_frames(self, frames):
    for detections in frames:
        ev = evaluate(detections, self.cp.profile)
        self.cp.update(ev, self.t)
        result = self.cp.pop_finalized()
        if result is not None:
            self.results.append(result)
        self.t += self.step
    return self.cp.snapshot(self.t)


Driver.feed_frames = _feed_frames


def wait_for(condition, timeout=3.0, interval=0.01):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(interval)
    return condition()
