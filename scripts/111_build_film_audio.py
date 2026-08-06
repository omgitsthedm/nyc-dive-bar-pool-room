"""111_build_film_audio.py - deterministic, physics-timed mix for the film.

Every hit is placed at the solver's own event time. Nothing is hand-timed and
nothing is performed: the same trajectory in gives the same WAV out, bit for
bit, because the RNG is seeded from the trajectory hash.

Numbered 111, not 110 - 110 is the guarded deploy script.

PATH B (offline synthesis) is used. No CC0 sample could be license-verified
without a network fetch, and the provenance invariant says synthesize rather
than ship an asset whose licence cannot be proven. The generator is recorded
in docs/SOURCE_MANIFEST.md; synthesized assets need no manifest entry.

Run with the project venv python (numpy only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SR = 48000
FILM_LEN_S = 30.0
PAN_SCALE = 0.20
ROOM_TONE_DBFS = -34.0
TARGET_PEAK_DBFS = -1.0
OVERLAP_WINDOW_S = 0.05
OVERLAP_CAP = 6


def film_offset_s():
    """The ONE mapping constant, read from the render script so picture and
    sound can never disagree about when the strike happens."""
    text = (ROOT / "scripts" / "105_render_film.py").read_text()
    for line in text.splitlines():
        if line.startswith("FILM_OFFSET_S"):
            return float(line.split("=")[1].split("#")[0].strip())
    raise RuntimeError("could not read FILM_OFFSET_S from 105_render_film.py")


def _env(n_attack, n_decay, curve=6.0):
    a = np.linspace(0.0, 1.0, max(n_attack, 1))
    d = np.exp(-np.linspace(0.0, curve, max(n_decay, 1)))
    return np.concatenate([a, d])


def _band(rng, n, lo, hi):
    noise = rng.standard_normal(n)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    spec[(freqs < lo) | (freqs > hi)] = 0.0
    out = np.fft.irfft(spec, n)
    return out / (np.abs(out).max() + 1e-9)


def _norm(s):
    return s / (np.abs(s).max() + 1e-9)


def synth_clack(rng):
    """Phenolic on phenolic: bright, short, with a ringing partial."""
    n = int(0.068 * SR)
    body = _band(rng, n, 2000, 6000)
    t = np.arange(n) / SR
    partial = np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 55.0) * 0.35
    env = _env(int(0.0015 * SR), n - int(0.0015 * SR), 7.0)[:n]
    return _norm((body + partial) * env)


def synth_cushion(rng):
    """Cloth over rubber: no top end, gone in a tenth of a second."""
    n = int(0.12 * SR)
    body = _band(rng, n, 150, 400)
    env = _env(int(0.004 * SR), n - int(0.004 * SR), 5.0)[:n]
    return _norm(body * env)


def synth_pocket(rng):
    """Leather pluck plus the basket taking the weight."""
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 9.0)
    pluck = _band(rng, n, 400, 2200) * np.exp(-t * 26.0) * 0.55
    rumble = _band(rng, n, 45, 160) * np.exp(-t * 5.0) * 0.7
    return _norm(thud + pluck + rumble)


def synth_crack(rng):
    """The cue strike: the loudest single sound in the film."""
    n = int(0.09 * SR)
    body = _band(rng, n, 1200, 7000)
    t = np.arange(n) / SR
    snap = rng.standard_normal(n) * np.exp(-t * 260.0) * 0.9
    low = np.sin(2 * np.pi * 220 * t) * np.exp(-t * 30.0) * 0.3
    env = _env(int(0.0008 * SR), n - int(0.0008 * SR), 8.0)[:n]
    return _norm((body + snap + low) * env)


def room_tone(rng, n):
    """Brown noise under 300 Hz - a bar with a compressor running somewhere.

    Band-limited 25-300 Hz and normalised by RMS, not by peak. Brown noise is
    a random walk: it wanders, so one large excursion scales a peak-normalised
    bed into near-silence everywhere else. Measured on the first attempt, the
    tone ran -74 dBFS early and -48 dBFS late - a 26 dB drift under a mix that
    is supposed to sit on a steady -34 dBFS floor. The 25 Hz corner removes
    the DC wander; RMS normalisation puts the bed where it was specified.
    """
    w = np.cumsum(rng.standard_normal(n))
    spec = np.fft.rfft(w)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    spec[(freqs < 25.0) | (freqs > 300.0)] = 0.0
    tone = np.fft.irfft(spec, n)
    rms = float(np.sqrt(np.mean(tone ** 2)))
    return tone / (rms + 1e-12) * (10 ** (ROOM_TONE_DBFS / 20.0))


SOUND_FOR = {
    "stick_ball": ("crack", 1.00),
    "ball_ball": ("clack", 1.00),
    "ball_linear_cushion": ("cushion", 10 ** (-8 / 20)),
    "ball_circular_cushion": ("cushion", 10 ** (-8 / 20)),
    "ball_pocket": ("pocket", 1.00),
}


def impact_speed(event):
    vs = [np.array(b["initial"]["velocity_mps"], dtype=float)
          for b in event["balls"]]
    if len(vs) == 1:
        return float(np.linalg.norm(vs[0]))
    return float(np.linalg.norm(vs[0] - vs[1]))


def pan_of(event, half_w=0.635):
    xs = [float(b["initial"]["position_m"][0]) for b in event["balls"]]
    return float(np.clip(((np.mean(xs) - half_w) / half_w) * PAN_SCALE,
                         -1.0, 1.0))


def build(shot_path, out_dir):
    data = json.loads(Path(shot_path).read_text())
    assert data["schema"] == "pool-shot-trajectory/v1"
    offset = film_offset_s()
    rng = np.random.default_rng(int(data["trajectory_sha256"][:8], 16))
    banks = {"crack": synth_crack(rng), "clack": synth_clack(rng),
             "cushion": synth_cushion(rng), "pocket": synth_pocket(rng)}

    n_total = int(FILM_LEN_S * SR)
    left = np.zeros(n_total)
    right = np.zeros(n_total)

    audible = [e for e in data["events"] if e["type"] in SOUND_FOR]
    # Cap simultaneous overlaps at the 6 loudest per 50 ms so the first
    # instant after impact cannot clip into mush.
    audible.sort(key=lambda e: (round(e["time_s"] / OVERLAP_WINDOW_S),
                                -impact_speed(e)))
    window_counts = {}
    placed, dropped = [], []
    for e in audible:
        w = round(e["time_s"] / OVERLAP_WINDOW_S)
        window_counts[w] = window_counts.get(w, 0) + 1
        if window_counts[w] > OVERLAP_CAP:
            dropped.append({"type": e["type"], "time_s": e["time_s"]})
            continue
        t = e["time_s"] + offset
        if t >= FILM_LEN_S:
            dropped.append({"type": e["type"], "time_s": e["time_s"],
                            "reason": "past end of film"})
            continue
        key, trim = SOUND_FOR[e["type"]]
        v = impact_speed(e)
        gain = float(np.clip((v / 8.0) ** 0.7, 0.12, 1.0)) * trim
        s = banks[key]
        rate = 1.0 + (rng.random() - 0.5) * 0.06        # +/-3% pitch
        idx = np.clip((np.arange(int(len(s) / rate)) * rate).astype(int),
                      0, len(s) - 1)
        s = s[idx] * gain
        i0 = int(t * SR)
        i1 = min(i0 + len(s), n_total)
        pan = pan_of(e)
        lg, rg = math.sqrt(0.5 * (1 - pan)), math.sqrt(0.5 * (1 + pan))
        left[i0:i1] += s[:i1 - i0] * lg
        right[i0:i1] += s[:i1 - i0] * rg
        placed.append({"type": e["type"], "time_s": round(e["time_s"], 5),
                       "film_time_s": round(t, 5), "gain": round(gain, 5),
                       "impact_mps": round(v, 4), "pan": round(pan, 4),
                       "ids": e.get("ids", [])})

    tone = room_tone(rng, n_total)
    # Fade the bed in and out so it does not click at the head or tail.
    fade = int(1.2 * SR)
    ramp = np.ones(n_total)
    ramp[:fade] = np.linspace(0.0, 1.0, fade)
    ramp[-fade:] = np.linspace(1.0, 0.0, fade)
    tone = tone * ramp
    left += tone
    right += tone

    peak = float(max(np.abs(left).max(), np.abs(right).max()))
    target = 10 ** (TARGET_PEAK_DBFS / 20.0)
    if peak > target:
        left *= target / peak
        right *= target / peak
    true_peak = float(max(np.abs(left).max(), np.abs(right).max()))

    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / "film_mix.wav"
    pcm = np.stack([left, right], axis=1)
    pcm16 = (np.clip(pcm, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm16.tobytes())

    manifest = {
        "shot": str(Path(shot_path).relative_to(ROOT)),
        "trajectory_sha256": data["trajectory_sha256"],
        "film_offset_s": offset,
        "sample_rate": SR,
        "events_in_trajectory": len(data["events"]),
        "events_audible": len(audible),
        "events_placed": len(placed),
        "events_dropped_overlap_cap": len(dropped),
        "true_peak_dbfs": round(20 * math.log10(true_peak + 1e-12), 3),
        "room_tone_dbfs": ROOM_TONE_DBFS,
        "wav_sha256": hashlib.sha256(wav_path.read_bytes()).hexdigest(),
        "placed": placed,
        "dropped": dropped,
    }
    (ROOT / "reports" / "film_audio_manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n")

    print("  [audio] %d audible events, %d placed, %d dropped by the "
          "overlap cap" % (len(audible), len(placed), len(dropped)))
    print("  [audio] true peak %.2f dBFS (target %.1f)"
          % (manifest["true_peak_dbfs"], TARGET_PEAK_DBFS))
    print("  [audio] strike at film %.2fs; first hard sound in the mix at "
          "%.2fs" % (offset, min(p["film_time_s"] for p in placed)))
    print("  [audio] %s" % wav_path)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot",
                    default=str(ROOT / "assets/data/shots/break_film.json"))
    ap.add_argument("--out", default=str(ROOT / "renders/film_audio"))
    a = ap.parse_args()
    raise SystemExit(build(a.shot, Path(a.out)))
