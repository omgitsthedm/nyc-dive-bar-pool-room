"""107_prove_top_candidates.py - Section 5.3 proofs for the top-3 breaks.

For each finalist from reports/break_sweep.json:
  1. write its candidate tuple            assets/data/shots/candidates/<id>.json
  2. export the full 240 Hz trajectory    assets/data/shots/candidates/out/<id>.json
  3. bake into a THROWAWAY blend          (102 --shot ... --out <scratch>)
  4. render the proof set                 renders/break_candidates/<id>/

The real gameplay blend is never touched: step 3 always writes to a scratch
path. The frozen control break stays the regression fixture throughout.

Run with the project venv python from the repo root.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT.parent / ".venv" / "bin" / "python"
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
PREVIEW_BLEND = ROOT / "blend" / "poolroom_pool_rebuild_preview.blend"
SWEEP_REPORT = ROOT / "reports" / "break_sweep.json"
CAND_DIR = ROOT / "assets" / "data" / "shots" / "candidates"
PROOF_ROOT = ROOT / "renders" / "break_candidates"
SCRATCH = Path(os.environ.get(
    "POOLROOM_SCRATCH",
    "/private/tmp/claude-501/-Users-davidmarsh/"
    "c39e782c-72e9-4574-9e59-738f4ddc90f8/scratchpad")) / "candidate_blends"


def run(cmd, label):
    started = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + "\n" + proc.stderr[-4000:])
        raise RuntimeError("%s failed (exit %d)" % (label, proc.returncode))
    print("    %-28s %6.1fs" % (label, time.time() - started))
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--resolution", default="1280x720")
    args = ap.parse_args()

    report = json.loads(SWEEP_REPORT.read_text())
    by_id = {r["id"]: r for r in report["results"]}
    finalists = [by_id[i] for i in report["top"][:args.top]]
    if not finalists:
        raise RuntimeError("sweep report has no accepted candidates")

    CAND_DIR.mkdir(parents=True, exist_ok=True)
    (CAND_DIR / "out").mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)

    summary = []
    for row in finalists:
        cid = row["id"]
        print("  [proof] %s  score=%.2f pocketed=%d rails=%d spread=%.3f"
              % (cid, row["score"], row["balls_pocketed"], row["rails_hit"],
                 row["spread_m"]))
        shot_path = CAND_DIR / ("%s.json" % cid)
        shot_path.write_text(json.dumps({
            k: row[k] for k in ("id", "cue_ball_y_offset_m", "speed_mps",
                                "aim_jitter_deg", "a", "b", "theta_deg")
        }, indent=1) + "\n")

        traj = CAND_DIR / "out" / ("%s.json" % cid)
        run([str(VENV_PY), str(ROOT / "scripts" / "101_export_pool_shot.py"),
             "--shot", str(shot_path), "--out", str(traj)],
            "export trajectory")

        throwaway = SCRATCH / ("gameplay_%s.blend" % cid)
        run([BLENDER, "-b", str(PREVIEW_BLEND), "-P",
             str(ROOT / "scripts" / "102_bake_pool_playback.py"), "--",
             "--shot", str(traj), "--out", str(throwaway)],
            "bake throwaway blend")

        out_dir = PROOF_ROOT / cid
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        run([BLENDER, "-b", str(throwaway), "-P",
             str(ROOT / "scripts" / "108_render_candidate_proof.py"), "--",
             "--id", cid, "--out", str(out_dir),
             "--resolution", args.resolution],
            "render proof set")

        payload = json.loads(traj.read_text())
        summary.append({
            "id": cid,
            "trajectory_sha256": payload["trajectory_sha256"],
            "balls_pocketed": row["balls_pocketed"],
            "rails_hit": row["rails_hit"],
            "spread_m": row["spread_m"],
            "settle_s": row["settle_s"],
            "duration_s": row["duration_s"],
            "eight_survives": row["eight_survives"],
            "score": row["score"],
            "proof_dir": str(out_dir.relative_to(ROOT)),
        })

    out = ROOT / "reports" / "break_finalists.json"
    out.write_text(json.dumps({"finalists": summary}, indent=1) + "\n")
    print()
    print("  [proof] wrote %s" % out)
    for s in summary:
        print("     %s  pocketed=%d rails=%d spread=%.3f m settle=%.2fs "
              "8ball=%s" % (s["id"], s["balls_pocketed"], s["rails_hit"],
                            s["spread_m"], s["settle_s"], s["eight_survives"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
