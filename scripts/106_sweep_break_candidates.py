"""106_sweep_break_candidates.py - Section 5 deterministic break sweep.

Cue placement, speed, aim and tip offset are SOLVER INPUTS, so a candidate is
a parameter tuple and the whole sweep is reproducible. Nothing here rolls
dice: the same grid in gives the same 90 trajectories out, every time.

Pipeline:
  1. write the candidate grid          -> assets/data/shots/candidates/breaks_sweep.json
  2. simulate all 90 (solver only)
  3. cull against the Section 5.2 rules
  4. score survivors, rank, keep top 3 -> reports/break_sweep.json

Run with the project venv python, from the repo root.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_game_physics as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SWEEP_JSON = ROOT / "assets" / "data" / "shots" / "candidates" / "breaks_sweep.json"
REPORT = ROOT / "reports" / "break_sweep.json"

# Section 5.1 grid: 5 x 3 x 2 x 3 = 90.
HEAD_STRING_OFFSETS = (-0.10, -0.05, 0.0, 0.05, 0.10)
SPEEDS = (9.8, 10.73, 11.6)          # cue ball m/s, ~22-26 mph
VERTICAL_B = (0.0, 0.12)             # a touch of follow
AIM_JITTER = (0.0, -0.15, 0.15)

# Section 5.2 thresholds.
MIN_OBJECT_BALLS_TO_CUSHION = 4
MIN_BALLS_MOVED = 12
MOVED_DISTANCE_M = 0.150
MAX_SETTLE_S = 12.0

OBJECT_IDS = tuple(str(n) for n in range(1, 16))


def build_grid() -> list[dict]:
    rows = []
    for i, (off, speed, b, jitter) in enumerate(itertools.product(
            HEAD_STRING_OFFSETS, SPEEDS, VERTICAL_B, AIM_JITTER)):
        rows.append({
            "id": "b_%02d" % i,
            "cue_ball_y_offset_m": off,
            "speed_mps": speed,
            "aim_jitter_deg": jitter,
            "a": 0.0,
            "b": b,
            "theta_deg": 0.0,
        })
    return rows


def _final_xy(ball: dict) -> tuple[float, float]:
    p = ball["samples"][-1]["p"]
    return float(p[0]), float(p[1])


def analyse(payload: dict, geometry: dict, rack: dict) -> dict:
    balls = payload["balls"]
    events = payload["events"]
    pockets = geometry["pockets"]
    ball_r = float(geometry["ball_R"])

    pocketed = {bid for bid, b in balls.items() if b.get("pocket_id")}
    scratched = "cue" in pocketed
    object_pocketed = sorted(pocketed - {"cue"})

    # Distinct OBJECT balls that touched a cushion (rule 2 counts balls, not
    # events - twenty rail contacts from one ball is not a legal break).
    cushion_balls = set()
    rails_hit = 0
    for e in events:
        if e["type"] != "ball_linear_cushion":
            continue
        rails_hit += 1
        for b in e.get("balls", []):
            if b["id"] != "cue":
                cushion_balls.add(b["id"])

    # Rule 3: object balls that ended far enough from where they were racked.
    rack_xy = rack["positions_pool_xy_m"]
    moved = 0
    finals = {}
    for bid in OBJECT_IDS:
        if bid not in balls:
            continue
        fx, fy = _final_xy(balls[bid])
        finals[bid] = (fx, fy)
        if bid in pocketed:
            moved += 1                      # a pocketed ball certainly moved
            continue
        rx, ry = rack_xy[bid]
        if math.hypot(fx - float(rx), fy - float(ry)) >= MOVED_DISTANCE_M:
            moved += 1

    # Settle time: the last moment anything stopped rolling.
    stops = [e["time_s"] for e in events if e["type"] == "rolling_stationary"]
    settle = max(stops) if stops else float(payload["duration_s"])

    # Rule 5: a ball at rest overlapping a pocket circle is sitting in the jaw
    # and blocks it. Reads as broken to a lay viewer even though it is legal.
    blockers = []
    for bid, (fx, fy) in finals.items():
        if bid in pocketed:
            continue
        for pid, pk in pockets.items():
            cx, cy = float(pk["center"][0]), float(pk["center"][1])
            if math.hypot(fx - cx, fy - cy) < float(pk["radius"]) + ball_r:
                blockers.append("%s@%s" % (bid, pid))
                break
    if not scratched and "cue" in balls:
        cfx, cfy = _final_xy(balls["cue"])
        for pid, pk in pockets.items():
            cx, cy = float(pk["center"][0]), float(pk["center"][1])
            if math.hypot(cfx - cx, cfy - cy) < float(pk["radius"]) + ball_r:
                blockers.append("cue@%s" % pid)
                break

    # Spread: mean final distance from the rack centroid, in metres.
    rxs = [float(rack_xy[b][0]) for b in OBJECT_IDS if b in rack_xy]
    rys = [float(rack_xy[b][1]) for b in OBJECT_IDS if b in rack_xy]
    ccx, ccy = sum(rxs) / len(rxs), sum(rys) / len(rys)
    dists = [math.hypot(fx - ccx, fy - ccy) for fx, fy in finals.values()]
    spread = sum(dists) / len(dists) if dists else 0.0

    eight_survives = "8" not in pocketed

    rejects = []
    if scratched:
        rejects.append("scratch")
    if len(cushion_balls) < MIN_OBJECT_BALLS_TO_CUSHION:
        rejects.append("only_%d_object_balls_to_cushion" % len(cushion_balls))
    if moved < MIN_BALLS_MOVED:
        rejects.append("only_%d_of_15_balls_moved_150mm" % moved)
    if settle > MAX_SETTLE_S:
        rejects.append("settle_%.2fs_over_%.0fs" % (settle, MAX_SETTLE_S))
    if blockers:
        rejects.append("jaw_blocked_" + "+".join(blockers))

    score = (len(object_pocketed) * 3
             + rails_hit
             + spread
             + (2 if eight_survives else 0))

    return {
        "balls_pocketed": len(object_pocketed),
        "pocketed_ids": object_pocketed,
        "scratched": scratched,
        "rails_hit": rails_hit,
        "object_balls_to_cushion": len(cushion_balls),
        "balls_moved_150mm": moved,
        "settle_s": round(settle, 4),
        "duration_s": round(float(payload["duration_s"]), 4),
        "spread_m": round(spread, 5),
        "eight_survives": eight_survives,
        "jaw_blockers": blockers,
        "score": round(score, 5),
        "rejects": rejects,
        "accepted": not rejects,
        "trajectory_sha256": payload["trajectory_sha256"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="simulate only the first N candidates (smoke test)")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()

    grid = build_grid()
    SWEEP_JSON.parent.mkdir(parents=True, exist_ok=True)
    SWEEP_JSON.write_text(json.dumps(grid, indent=1) + "\n")
    print("  [sweep] wrote %d candidates -> %s" % (len(grid), SWEEP_JSON))

    profile = P.load_profile()
    geometry = P.load_geometry()
    rate = int(profile["solver"]["sample_rate_hz"])
    rows = grid[:args.limit] if args.limit else grid

    results = []
    t0 = time.time()
    for n, shot in enumerate(rows, 1):
        overrides = {
            "head_string_offset_m": shot["cue_ball_y_offset_m"],
            "cue_ball_speed_mps": shot["speed_mps"],
            "aim_jitter_deg": shot["aim_jitter_deg"],
            "a": shot["a"], "b": shot["b"], "theta_deg": shot["theta_deg"],
        }
        system = P.control_break_system(profile, geometry, overrides=overrides)
        P.simulate(system, profile=profile)
        payload = P.export_trajectory(system, shot_id=shot["id"],
                                      profile=profile, geometry=geometry,
                                      sample_rate_hz=rate)
        row = analyse(payload, geometry, payload["rack"])
        row.update({k: shot[k] for k in
                    ("id", "cue_ball_y_offset_m", "speed_mps",
                     "aim_jitter_deg", "a", "b", "theta_deg")})
        results.append(row)
        flag = "OK  " if row["accepted"] else "cull"
        print("  [%3d/%3d] %s %s  pocketed=%d rails=%2d spread=%.3f "
              "settle=%.2f score=%.2f %s"
              % (n, len(rows), flag, row["id"], row["balls_pocketed"],
                 row["rails_hit"], row["spread_m"], row["settle_s"],
                 row["score"], ";".join(row["rejects"])))

    survivors = [r for r in results if r["accepted"]]
    survivors.sort(key=lambda r: (-r["score"], r["id"]))
    top = survivors[:args.top]

    report = {
        "grid": {"head_string_offsets_m": list(HEAD_STRING_OFFSETS),
                 "cue_ball_speeds_mps": list(SPEEDS),
                 "vertical_offset_b": list(VERTICAL_B),
                 "aim_jitter_deg": list(AIM_JITTER),
                 "total": len(grid)},
        "rules": {"min_object_balls_to_cushion": MIN_OBJECT_BALLS_TO_CUSHION,
                  "min_balls_moved": MIN_BALLS_MOVED,
                  "moved_distance_m": MOVED_DISTANCE_M,
                  "max_settle_s": MAX_SETTLE_S},
        "simulated": len(results),
        "accepted": len(survivors),
        "culled": len(results) - len(survivors),
        "top": [r["id"] for r in top],
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1) + "\n")

    print()
    print("  [sweep] simulated %d in %.1fs; %d accepted, %d culled"
          % (len(results), time.time() - t0, len(survivors),
             len(results) - len(survivors)))
    print("  [sweep] TOP %d:" % len(top))
    for r in top:
        print("     %s score=%.2f pocketed=%d rails=%d spread=%.3f "
              "settle=%.2fs 8ball=%s  (offset %+.2f speed %.2f b %.2f "
              "jitter %+.2f)"
              % (r["id"], r["score"], r["balls_pocketed"], r["rails_hit"],
                 r["spread_m"], r["settle_s"], r["eight_survives"],
                 r["cue_ball_y_offset_m"], r["speed_mps"], r["b"],
                 r["aim_jitter_deg"]))
    print("  [sweep] report -> %s" % REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
