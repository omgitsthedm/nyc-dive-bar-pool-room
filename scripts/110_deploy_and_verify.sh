#!/usr/bin/env bash
# 110_deploy_and_verify.sh - guarded deploy + byte verification.
#
# INVARIANT (handoff section 0): this Netlify account hosts other client sites
# and an unflagged deploy once landed on the wrong one. The deploy is pinned to
# the site id in ../.netlify-site-id and the output is checked for the expected
# host before anything is treated as shipped.
#
# Then every published asset is fetched back from the live URL and compared
# byte-for-byte against the local file. "It deployed" is not evidence that the
# right bytes are being served.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
SITE_ID_FILE="$REPO/../.netlify-site-id"
EXPECT_HOST="pool-table-test"

[ -f "$SITE_ID_FILE" ] || { echo "MISSING $SITE_ID_FILE - ABORT"; exit 1; }
SITE_ID="$(tr -d '[:space:]' < "$SITE_ID_FILE")"
[ -n "$SITE_ID" ] || { echo "EMPTY site id - ABORT"; exit 1; }

echo "=== deploying to site id ${SITE_ID:0:8}... (expect host: $EXPECT_HOST) ==="
out="$(netlify deploy --prod --dir site --site "$SITE_ID" 2>&1)"
status=$?
echo "$out" | tail -20

if ! echo "$out" | grep -qi "$EXPECT_HOST"; then
  echo
  echo "WRONG SITE - ABORT. Deploy output never mentioned '$EXPECT_HOST'."
  echo "Nothing further will be verified. Check the site id before retrying."
  exit 1
fi
[ $status -eq 0 ] || { echo "netlify deploy exited $status - ABORT"; exit 1; }

BASE="https://${EXPECT_HOST}.netlify.app"
echo
echo "=== byte-verifying published assets against $BASE ==="
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail=0
total=0

verify() {
  local rel="$1" local_path="$REPO/site/$1"
  [ -f "$local_path" ] || return 0
  total=$((total + 1))
  local dl="$tmp/$(echo "$rel" | tr '/' '_')"
  if ! curl -fsSL --max-time 60 "$BASE/$rel" -o "$dl"; then
    echo "  FETCH FAILED  $rel"
    fail=$((fail + 1)); return 0
  fi
  if cmp -s "$local_path" "$dl"; then
    echo "  ok            $rel  ($(wc -c < "$dl" | tr -d ' ') bytes)"
  else
    echo "  BYTE MISMATCH $rel  local=$(wc -c < "$local_path" | tr -d ' ') live=$(wc -c < "$dl" | tr -d ' ')"
    fail=$((fail + 1))
  fi
}

for f in "$REPO"/site/img/opening/*.webp; do
  verify "img/opening/$(basename "$f")"
done
for extra in "$@"; do
  verify "$extra"
done

echo
if [ "$fail" -ne 0 ]; then
  echo "VERIFY FAILED: $fail of $total assets differ from local - NOT SHIPPED CLEAN"
  exit 1
fi
echo "VERIFIED: all $total assets match local byte-for-byte at $BASE"
