#!/bin/sh
# On the WEBSITE server (194.238.27.60): the only thing the pool server's key may run here (the `command=` of its line in
# ~tenero-pool-stats/.ssh/authorized_keys). It reads the pool's stats file from the connection, at most 4 MiB, checks that it
# looks like one, and puts it in place whole. It cannot run anything else, read anything, or write anywhere else.
set -eu
DIR=/var/www/teneronetwork/pool-stats
TMP="$DIR/pool.json.tmp"
head -c 4194304 > "$TMP"
case "$(head -c 11 "$TMP")" in
  '{"format":1') ;;
  *) rm -f "$TMP"; echo "not a pool stats file" >&2; exit 1 ;;
esac
chmod 644 "$TMP"
mv -f "$TMP" "$DIR/pool.json"
