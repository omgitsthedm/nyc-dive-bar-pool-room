"""Export the deterministic control break as solver-authoritative JSON."""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_game_physics as P  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "assets" / "data" / "shots" / "break_control.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="break_control",
                        choices=("break_control",))
    parser.add_argument("--sample-rate", type=int, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    profile = P.load_profile()
    geometry = P.load_geometry()
    rate = args.sample_rate or int(profile["solver"]["sample_rate_hz"])
    if rate < 120:
        raise ValueError("authoritative trajectory exports require at least 120 Hz")

    system = P.control_break_system(profile, geometry)
    P.simulate(system, profile=profile)
    payload = P.export_trajectory(
        system,
        shot_id=args.fixture,
        profile=profile,
        geometry=geometry,
        sample_rate_hz=rate,
    )
    payload["generated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    P.verify_trajectory_sha256(payload)
    P.write_json(args.out, payload, compact=True)
    P.verify_trajectory_sha256(P.load_json(args.out))
    print("  [shot export] %s" % args.out)
    print("  [duration] %.3f s solver / %.3f s playback" %
          (payload["solver_duration_s"], payload["duration_s"]))
    print("  [events] %d" % len(payload["events"]))
    print("  [trajectory] %s" % payload["trajectory_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
