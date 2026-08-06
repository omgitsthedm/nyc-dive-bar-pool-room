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


def load_candidate(path: Path) -> dict:
    """One candidate tuple from the Section 5.1 sweep schema.

    {"id","cue_ball_y_offset_m","speed_mps","aim_jitter_deg","a","b",
     "theta_deg"}. The schema calls the placement field
     ``cue_ball_y_offset_m`` but describes it as "along the head string"; the
     control break aims down -Y, so the head string is pool X and that is
     where the offset is applied. ``speed_mps`` is CUE BALL speed, matching
     the profile's target_cue_ball_speed_mps, not the stick's V0.
    """
    shot = P.load_json(path)
    required = ("id", "cue_ball_y_offset_m", "speed_mps")
    missing = [k for k in required if k not in shot]
    if missing:
        raise ValueError("candidate %s missing keys: %s" %
                         (path, ", ".join(missing)))
    overrides = {
        "head_string_offset_m": float(shot["cue_ball_y_offset_m"]),
        "cue_ball_speed_mps": float(shot["speed_mps"]),
        "aim_jitter_deg": float(shot.get("aim_jitter_deg", 0.0)),
    }
    for key in ("a", "b", "theta_deg"):
        if key in shot:
            overrides[key] = float(shot[key])
    return shot, overrides


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="break_control",
                        choices=("break_control",))
    parser.add_argument("--sample-rate", type=int, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--shot", type=Path, default=None,
                        help="candidate JSON (Section 5.1 schema); without "
                             "this the frozen control break is exported and "
                             "its trajectory hash must not move")
    args = parser.parse_args()

    profile = P.load_profile()
    geometry = P.load_geometry()
    rate = args.sample_rate or int(profile["solver"]["sample_rate_hz"])
    if rate < 120:
        raise ValueError("authoritative trajectory exports require at least 120 Hz")

    shot_id = args.fixture
    overrides = None
    if args.shot is not None:
        shot, overrides = load_candidate(args.shot)
        shot_id = str(shot["id"])

    system = P.control_break_system(profile, geometry, overrides=overrides)
    P.simulate(system, profile=profile)
    payload = P.export_trajectory(
        system,
        shot_id=shot_id,
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
