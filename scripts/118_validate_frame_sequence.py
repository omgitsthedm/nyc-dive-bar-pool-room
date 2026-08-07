"""118_validate_frame_sequence.py - the gate on the rendered frames themselves.

Runs on the PNG sequence before anything is encoded. It is the check that the
film this replaces could not have survived: that one rendered one frame per
static shot and copied it, so two thirds of its frames were byte-identical to
their neighbour. Here that is a hard failure.

  * exactly 720 files, numbered 0000..0719, no gaps
  * no two consecutive frames identical (byte hash)
  * no frame repeated anywhere in the film (catches a copied shot)
  * every shot's first, middle and last frame passes bit-depth-aware
    luminance analysis and is neither black nor washed out
  * the two pocket frames and the final-stop frame exist and are readable

Uses pngstats for every luminance number, because it is the one reader in this
project that handles 8- and 16-bit PNGs correctly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import film_time as FT            # noqa: E402
from pngstats import luminance_stats  # noqa: E402

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  [%s] %-38s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--min-mean", type=float, default=0.030)
    ap.add_argument("--max-mean", type=float, default=0.80)
    ap.add_argument("--stride", type=int, default=13,
                    help="pixel stride for the luminance sampling")
    args = ap.parse_args()

    frames = Path(args.frames)
    man = json.load(open(args.manifest))

    files = sorted(frames.glob("[0-9][0-9][0-9][0-9].png"))
    check("frame_count_is_720", len(files) == FT.TOTAL_FRAMES,
          "%d PNG files in %s" % (len(files), frames))

    nums = [int(p.stem) for p in files]
    missing = [n for n in range(FT.TOTAL_FRAMES) if n not in set(nums)]
    check("numbering_0000_to_0719_no_gaps", not missing,
          "first=%04d last=%04d missing=%d%s"
          % (min(nums), max(nums), len(missing),
             (" e.g. %s" % missing[:5]) if missing else ""))

    # --- duplicate detection ------------------------------------------------
    hashes = {}
    for p in files:
        hashes[int(p.stem)] = hashlib.sha256(p.read_bytes()).hexdigest()
    consec = [n for n in range(1, FT.TOTAL_FRAMES)
              if n in hashes and (n - 1) in hashes
              and hashes[n] == hashes[n - 1]]
    check("no_consecutive_duplicate_frames", not consec,
          "%d consecutive identical pairs%s"
          % (len(consec), (" at %s" % consec[:8]) if consec else ""))

    seen = {}
    repeats = []
    for n, h in sorted(hashes.items()):
        if h in seen:
            repeats.append((seen[h], n))
        else:
            seen[h] = n
    check("no_repeated_frame_anywhere", not repeats,
          "%d distinct images across %d frames%s"
          % (len(seen), len(hashes),
             ("; repeats %s" % repeats[:6]) if repeats else ""))

    # --- luminance per shot -------------------------------------------------
    rows = []
    bad = []
    for sh in man["shots"]:
        picks = [sh["first"], (sh["first"] + sh["last"]) // 2, sh["last"]]
        for f in picks:
            p = frames / ("%04d.png" % f)
            if not p.exists():
                bad.append((f, "missing"))
                continue
            s = luminance_stats(p, stride_px=args.stride)
            rows.append(dict(shot=sh["shot"], name=sh["name"], frame=f,
                             mean=round(s["mean"], 5),
                             median=round(s["median"], 5),
                             p05=round(s["p05"], 5), p95=round(s["p95"], 5),
                             dark=round(s["frac_below_0_05"], 4),
                             bright=round(s["frac_above_0_50"], 4),
                             bit_depth=s["bit_depth"]))
            if s["mean"] < args.min_mean:
                bad.append((f, "too dark, mean %.4f" % s["mean"]))
            elif s["mean"] > args.max_mean:
                bad.append((f, "washed out, mean %.4f" % s["mean"]))
            elif s["frac_below_0_05"] > 0.90:
                bad.append((f, "%.0f%% of pixels below 0.05"
                            % (s["frac_below_0_05"] * 100)))
            elif s["frac_above_0_50"] > 0.75:
                bad.append((f, "%.0f%% of pixels above 0.50"
                            % (s["frac_above_0_50"] * 100)))
    print("    shot  frame   mean   median    p05    p95   dark  bright")
    for r in rows:
        print("    S%02d   %04d  %.4f  %.4f %.4f %.4f  %.3f  %.3f"
              % (r["shot"], r["frame"], r["mean"], r["median"], r["p05"],
                 r["p95"], r["dark"], r["bright"]))
    check("every_shot_first_mid_last_readable", not bad,
          "%d frames measured across %d shots; failures=%s"
          % (len(rows), len(man["shots"]), bad[:6] or "none"))

    # --- the moments the film exists for ------------------------------------
    # Derived from the shared offset, never hardcoded. These were literals -
    # 336/350/487 - left over from when the strike sat at 12.5 s. Moving the
    # strike to 19.0 s moved every event with it, and the gate went on
    # cheerfully measuring three frames that are now just ordinary cutaways.
    # A gate that checks the wrong frame is worse than no gate: it reports
    # PASS either way.
    key = {"7-ball pocket": FT.film_frame(1.5046 + FT.FILM_OFFSET_S),
           "4-ball pocket": FT.film_frame(2.0780 + FT.FILM_OFFSET_S),
           "last ball stops": FT.film_frame(7.805997761 + FT.FILM_OFFSET_S),
           "strike": FT.STRIKE_FRAME}
    kbad = []
    krows = []
    for label, f in sorted(key.items(), key=lambda kv: kv[1]):
        p = frames / ("%04d.png" % f)
        if not p.exists():
            kbad.append((label, "missing"))
            continue
        s = luminance_stats(p, stride_px=args.stride)
        krows.append(dict(label=label, frame=f, mean=round(s["mean"], 5),
                          dark=round(s["frac_below_0_05"], 4)))
        if s["mean"] < args.min_mean or s["frac_below_0_05"] > 0.90:
            kbad.append((label, "mean %.4f dark %.3f"
                         % (s["mean"], s["frac_below_0_05"])))
    for r in krows:
        print("    key %-16s frame %04d  mean %.4f  dark %.3f"
              % (r["label"], r["frame"], r["mean"], r["dark"]))
    check("key_event_frames_present_and_readable", not kbad,
          "strike, both pockets and the final stop; failures=%s"
          % (kbad or "none"))

    npass = sum(1 for _, p, _ in results if p)
    out = dict(frames_dir=str(frames), count=len(files),
               distinct_images=len(seen),
               consecutive_duplicates=consec, repeats=repeats,
               per_shot=rows, key_frames=krows,
               checks=[dict(name=n, passed=p, detail=d)
                       for n, p, d in results])
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.report, "w"), indent=1)
    print("=== frame sequence: %d/%d passed -> %s ==="
          % (npass, len(results), args.report))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
