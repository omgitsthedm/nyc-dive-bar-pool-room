"""pngstats.py - one correct PNG luminance reader, shared by the gates.

Written because the previous inline readers assumed 8 bits per channel.
Blender writes 16-bit PNGs by default, so an 8-bit reader walks the buffer
two bytes per channel out of step and reports the high and low bytes of red
as if they were red and green. That produces plausible-looking numbers from
meaningless data: a pitch-black film measured "mean 0.39" and sailed through
the black-frame check. Any gate that reads a render must use this.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


def decode(path):
    """-> (width, height, channels, bit_depth, bytes) with filters undone."""
    data = Path(path).read_bytes()
    pos, idat = 8, b""
    w = h = bd = ct = 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(idat)
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    bpp = nch * (bd // 8)
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    return w, h, nch, bd, bytes(out)


def luminance_stats(path, stride_px=1):
    """Rec.709 luma stats in 0..1. Handles 8- and 16-bit PNGs correctly."""
    w, h, nch, bd, px = decode(path)
    step = nch * (bd // 8)
    hi = (bd == 16)
    vals = []
    total = w * h
    for idx in range(0, total, max(stride_px, 1)):
        o = idx * step
        if hi:
            r, g, b = px[o], px[o + 2], px[o + 4]      # high byte of each
        else:
            r, g, b = px[o], px[o + 1], px[o + 2]
        vals.append((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0)
    vals.sort()
    n = len(vals)

    def pct(q):
        return vals[min(n - 1, max(0, int(q * n)))]

    return {
        "width": w, "height": h, "bit_depth": bd,
        "mean": sum(vals) / n,
        "median": pct(0.50),
        "p05": pct(0.05), "p95": pct(0.95),
        "frac_below_0_05": sum(1 for v in vals if v < 0.05) / n,
        "frac_above_0_50": sum(1 for v in vals if v > 0.50) / n,
    }
