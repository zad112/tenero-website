#!/bin/sh
# Writes the website's network panel (stats.json) from `tenerod status`.
# Runs as the node's own user (it needs the control cookie, which must never reach the web server);
# the web server only reads the JSON this writes. Run once a minute by tenero-web-stats.timer.
set -u
OUT=/var/www/teneronetwork/stats/stats.json
TMP="$OUT.tmp"
NOW=$(date +%s)

LINE=$(/opt/tenero-gamma/tenerod status --data /var/lib/tenero-gamma/data --control 127.0.0.1:38352 2>/dev/null)
# e.g. "network gamma | height 123 (1a2b3c4d) | peers 3 (in 2) | mempool 0 | in sync"
HEIGHT=$(printf '%s' "$LINE" | sed -n 's/.*| height \([0-9]*\) .*/\1/p')
PEERS=$(printf '%s' "$LINE" | sed -n 's/.*| peers \([0-9]*\) .*/\1/p')
MEMPOOL=$(printf '%s' "$LINE" | sed -n 's/.*| mempool \([0-9]*\) .*/\1/p')
case "$LINE" in *"| syncing"*) SYNCING=true ;; *) SYNCING=false ;; esac

if [ -n "$HEIGHT" ] && [ -n "$PEERS" ] && [ -n "$MEMPOOL" ]; then
  printf '{"ok":true,"network":"gamma","height":%s,"peers":%s,"mempool":%s,"syncing":%s,"updated":%s}\n' \
    "$HEIGHT" "$PEERS" "$MEMPOOL" "$SYNCING" "$NOW" > "$TMP"
else
  printf '{"ok":false,"updated":%s}\n' "$NOW" > "$TMP"
fi
chmod 644 "$TMP"
mv -f "$TMP" "$OUT"
