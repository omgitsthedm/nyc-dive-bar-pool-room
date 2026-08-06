#!/usr/bin/env bash
# Waits for the sweep render, encodes it, updates the site, deploys, commits.
# Deploys ONLY with the explicit site id.
set -euo pipefail
P="$(cd "$(dirname "$0")/.." && pwd -P)"
SID=6672b41c-ca69-458a-852d-c156b4b13e64
cd "$P"

while pgrep -f swf.py > /dev/null; do sleep 30; done
N=$(ls renders/sweep/s_*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$N" -ge 288 ] || { echo "INCOMPLETE: $N/288 frames"; exit 1; }

ffmpeg -y -framerate 24 -i renders/sweep/s_%04d.png -c:v libx264 \
  -pix_fmt yuv420p -crf 18 -movflags +faststart site/sweep.mp4
ffmpeg -y -i site/sweep.mp4 -ss 9.5 -frames:v 1 -q:v 3 site/img/sweep_poster.jpg

python3 - <<'PY'
p = "site/index.html"
s = open(p).read()
old_start = s.find('  <figure>\n    <video src="break.mp4"')
old_end = s.find('</figure>', old_start) + len('</figure>')
new = '''  <figure>
    <video src="sweep.mp4" poster="img/sweep_poster.jpg" controls loop muted
           autoplay playsinline></video>
    <figcaption>Table sweep &middot; 12 s, 24 fps &middot; static scene, camera move only</figcaption>
  </figure>'''
s = s[:old_start] + new + s[old_end:]
s = s.replace("The break film above is the\n    earlier physics project, kept on the same site.",
              "The film above is a camera move over the static scene &mdash; no\n    physics, nothing in the room animates.")
open(p, "w").write(s)
print("site html updated")
PY

netlify deploy --prod --dir site --site "$SID" | tee /tmp/sweep-deploy.out
grep -q "pool-table-test" /tmp/sweep-deploy.out || { echo "WRONG SITE"; exit 1; }

git add -A
git -c user.email=info@afterhoursagenda.com -c user.name="David Marsh" \
  commit -q -m "sweep film: 12 s camera move over the static room

288 frames at 24 fps, EEVEE. Nothing in the scene animates -- this is a camera
move over static geometry, which is why it cannot flicker: no simulation, no
volumetric crawl, and the slate sits a cloth-thickness below the cloth so there
is no z-fighting.

EEVEE resolves ~15x faster than Cycles here, which is what makes 288 frames
practical. It gathers far less indirect light from these small practicals, so
85_render_sweep.py applies exposure and light-boost compensation at render time
only; the four required stills remain Cycles at 512 spp.

Built with Claude Code (LiFi NYC)" || true
echo "SWEEP FINISH COMPLETE"
