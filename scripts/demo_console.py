"""Demo konsol: jalankan alur pos cek dengan waktu simulasi (tanpa kamera, model, ESP32, maupun paket tambahan).

    python scripts/demo_console.py
    python scripts/demo_console.py --profil pekerja-proyek-desa --detik 45

Skenario bergantian: pekerja lengkap -> salah satu APD terbukti tidak dipakai -> APD terakhir tidak terlihat.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safework.checkpoint import Checkpoint, CheckpointConfig  # noqa: E402
from safework.evaluator import evaluate  # noqa: E402
from safework.fakes import ScriptedDetector  # noqa: E402
from safework.indicators import Indicator, Lamp  # noqa: E402
from safework.messages import headline_detail  # noqa: E402
from safework.profiles import default_profiles  # noqa: E402
from safework.schemas import Phase  # noqa: E402


class ConsoleIndicator(Indicator):
    def __init__(self, clock):
        self.clock = clock

    def set_lamp(self, lamp: Lamp) -> None:
        extra = "  + buzzer 3 bip" if lamp == Lamp.RED else ""
        print(f"[{self.clock():5.1f} dtk]   lampu -> {lamp.value}{extra}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profil", default="penyemprot-pestisida")
    ap.add_argument("--detik", type=float, default=45.0, help="lama simulasi (detik waktu simulasi)")
    args = ap.parse_args()

    profiles = {p.id: p for p in default_profiles()}
    if args.profil not in profiles:
        sys.exit(f"Profil tidak dikenal. Pilihan: {', '.join(profiles)}")
    profile = profiles[args.profil]

    t = 0.0
    clock = lambda: t  # noqa: E731
    detector = ScriptedDetector(lambda: profile, present_seconds=10.0, gap_seconds=4.0, clock=clock)
    checkpoint = Checkpoint(profile, CheckpointConfig())
    indicator = ConsoleIndicator(clock)

    print(f"Profil: {profile.name}  (wajib: " + ", ".join(
        r.item for r in profile.rules if r.requirement.value == "wajib") + ")\n")
    prev = Phase.WAITING
    shown_scenario = None
    while t < args.detik:
        detections = detector.detect()
        if detector.scenario != shown_scenario:
            shown_scenario = detector.scenario
            print(f"[{t:5.1f} dtk] --- skenario: {shown_scenario} ---")
        snap = checkpoint.update(evaluate(detections, profile), t)
        result = checkpoint.pop_finalized()
        if result is not None:
            headline, detail = headline_detail(snap)
            print(f"[{t:5.1f} dtk]   HASIL: {headline}. {detail}")
            indicator.show_status(result.status)
        elif prev == Phase.RESULT and snap.phase != Phase.RESULT:
            indicator.show_status(None)
        if snap.phase != prev and snap.phase in (Phase.CHECKING, Phase.WAITING):
            print(f"[{t:5.1f} dtk]   fase: {snap.phase.value}")
        prev = snap.phase
        t = round(t + 0.1, 1)


if __name__ == "__main__":
    main()
