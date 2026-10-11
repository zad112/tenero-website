#!/bin/sh
# On the POOL server (195.26.244.245): sends the pool's stats file to the website server, which keeps it for the pool page.
# Runs as the pool's user every 30 s (tenero-pool-stats-push.timer). The key can do nothing on the website server but hand
# over this file (receive-pool-stats.sh there). The website server's host key is pinned in known_hosts (see the README).
set -eu
STATS=/var/lib/tenero-gamma-pool/stats/pool.json
KEY=/var/lib/tenero-gamma-pool/stats-push/id_ed25519
HOSTS=/var/lib/tenero-gamma-pool/stats-push/known_hosts
[ -f "$STATS" ] || exit 0
exec ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
  -o UserKnownHostsFile="$HOSTS" -o StrictHostKeyChecking=yes \
  tenero-pool-stats@194.238.27.60 < "$STATS"
