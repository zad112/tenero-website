#!/usr/bin/env python3
"""Writes the website's network panel (stats.json) by asking the gamma seed on this server.

It speaks the node's own control protocol (the Tenero repository, docs/CONTROL_PROTOCOL.md) and sends only READ requests:
`auth` (the cookie), `info`, `chain_stats` and `headers`. Nothing on the node changes. It runs as the node's user, because the
cookie is in the node's data directory and anything holding it can stop the node; the web server only ever reads the JSON this
writes. Python's standard library only. Run once a minute by tenero-web-stats.timer.

If anything fails (the node is down, starting, or answers something this does not understand, as after a protocol change), it
writes {"ok": false, ...} and the page says "no reading" instead of showing numbers it cannot vouch for.
"""

import json
import os
import socket
import struct
import sys
import time

DATA_DIR = "/var/lib/tenero-gamma/data"
CONTROL = ("127.0.0.1", 38352)
OUT = "/var/www/teneronetwork/stats/stats.json"

# what the page shows: the latest blocks, and the window the hash rate is estimated over (the difficulty's own, 30 blocks,
# as the block explorer does)
LATEST = 20
HASHRATE_WINDOW = 30
MAX_FRAME = 16 * 1024 * 1024
TIMEOUT = 10

K_AUTH, K_INFO, K_HEADERS, K_CHAIN_STATS = 1, 9, 17, 19
ANSWER, K_ERROR = 0x80, 0xFF
MAX_HEADERS = 64
MAX_NAME = 64
MAX_TEXT = 512


class ProtocolError(Exception):
    pass


class Reader:
    """Strict decoding, as the protocol asks: a short payload or a byte left over is an error."""

    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if self.pos + n > len(self.data):
            raise ProtocolError("the answer is too short")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.take(8))[0]

    def flag(self):
        v = self.u8()
        if v not in (0, 1):
            raise ProtocolError("a flag that is not 0 or 1")
        return v == 1

    def text(self, limit):
        n = self.u32()
        if n > limit:
            raise ProtocolError("a text over its limit")
        try:
            return self.take(n).decode("utf-8")
        except UnicodeDecodeError:
            raise ProtocolError("a text that is not UTF-8")

    def end(self):
        if self.pos != len(self.data):
            raise ProtocolError("bytes after the end of the answer")


def decode_response(body):
    """One answer body (kind and payload) as a dict, for the kinds this script asks for (and errors)."""
    if not body:
        raise ProtocolError("an empty answer")
    kind, r = body[0], Reader(body[1:])
    if kind == K_AUTH | ANSWER:
        out = {"type": "authed"}
    elif kind == K_INFO | ANSWER:
        out = {
            "type": "info",
            "height": r.u64(),
            "tip_id": r.take(32).hex(),
            "peers": r.u32(),
            "inbound": r.u32(),
            "pruned_below": r.u64(),
            "mempool_txs": r.u32(),
            "syncing": r.flag(),
        }
        k = r.u8()
        if k not in (0, 1):
            raise ProtocolError("an unknown node kind")
        out["kind"] = "archive" if k == 0 else "pruned"
        out["network"] = r.text(MAX_NAME)
        out["version"] = r.text(MAX_NAME)
    elif kind == K_HEADERS | ANSWER:
        n = r.u32()
        if n > MAX_HEADERS:
            raise ProtocolError("too many block summaries")
        blocks = []
        for _ in range(n):
            blocks.append({
                "height": r.u64(),
                "id": r.take(32).hex(),
                "timestamp": r.u64(),
                "target": r.take(32).hex(),
                "cumulative_work": r.take(32).hex(),
                "weight": r.u64(),
                "tx_count": r.u32(),
                "coinbase_total": r.u64(),
            })
        out = {"type": "headers", "blocks": blocks}
    elif kind == K_CHAIN_STATS | ANSWER:
        out = {
            "type": "chain_stats",
            "height": r.u64(),
            "next_target": r.take(32).hex(),
            "cumulative_work": r.take(32).hex(),
            "next_reward": r.u64(),
            "emitted": r.u64(),
            "max_supply": r.u64(),
            "tail_reward": r.u64(),
            "block_time": r.u64(),
        }
    elif kind == K_ERROR:
        out = {"type": "error", "message": r.text(MAX_TEXT)}
    else:
        raise ProtocolError("an answer of an unexpected kind 0x%02x" % kind)
    r.end()
    return out


def frame(body):
    return struct.pack("<I", len(body)) + body


class Node:
    def __init__(self, address, cookie):
        self.sock = socket.create_connection(address, timeout=TIMEOUT)
        try:
            if self.ask(bytes([K_AUTH]) + cookie)["type"] != "authed":
                raise ProtocolError("the node did not accept the cookie")
        except BaseException:
            self.sock.close()
            raise

    def recv_exact(self, n):
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise ProtocolError("the node closed the connection")
            out += chunk
        return out

    def ask(self, body):
        self.sock.sendall(frame(body))
        (length,) = struct.unpack("<I", self.recv_exact(4))
        if not 1 <= length <= MAX_FRAME:
            raise ProtocolError("a frame of length %d" % length)
        answer = decode_response(self.recv_exact(length))
        if answer["type"] == "error":
            raise ProtocolError("the node answered: " + answer["message"])
        return answer

    def info(self):
        return self.ask(bytes([K_INFO]))

    def chain_stats(self):
        return self.ask(bytes([K_CHAIN_STATS]))

    def headers(self, start, count):
        return self.ask(bytes([K_HEADERS]) + struct.pack("<QH", start, count))["blocks"]

    def close(self):
        self.sock.close()


def difficulty(target_hex):
    """The expected number of attempts for a block: floor(2^256 / target), as the explorer works it out."""
    t = int(target_hex, 16)
    return (1 << 256) // t if t else None


def estimate_hashrate(blocks, window):
    """The work the blocks of the last `window` proved, over the time their timestamps say they took: the explorer's own
    estimate (`tenero-explorer` core.rs). `blocks` in any order. The genesis block is left out (its time is the launch,
    not a block found). None with fewer than two blocks, or when the timestamps do not go forward."""
    usable = sorted((b for b in blocks if b["height"] >= 1), key=lambda b: b["height"], reverse=True)
    if not usable:
        return None
    newest = usable[0]
    older = [b for b in usable[1:] if newest["height"] - b["height"] <= window]
    if not older:
        return None
    oldest = min(older, key=lambda b: b["height"])
    seconds = newest["timestamp"] - oldest["timestamp"]
    if seconds <= 0:
        return None
    work = int(newest["cumulative_work"], 16) - int(oldest["cumulative_work"], 16)
    if work < 0:
        return None
    return {
        "per_second": work / seconds,
        "blocks": newest["height"] - oldest["height"],
        "seconds": seconds,
    }


def build(info, stats, blocks, now):
    """The JSON the page reads. Amounts are in units (100,000,000 to a coin), as the node gives them."""
    rate = estimate_hashrate(blocks, HASHRATE_WINDOW)
    newest_first = sorted(blocks, key=lambda b: b["height"], reverse=True)
    return {
        "ok": True,
        "format": 2,
        "updated": now,
        "network": info["network"],
        "version": info["version"],
        "height": info["height"],
        "peers": info["peers"],
        "inbound": info["inbound"],
        "mempool": info["mempool_txs"],
        "syncing": info["syncing"],
        "units_per_coin": 100_000_000,
        # integers past 2^53 lose precision in a browser, so the difficulty is given as text too
        "difficulty": str(difficulty(stats["next_target"]) or 0),
        "next_reward": stats["next_reward"],
        "emitted": stats["emitted"],
        "max_supply": stats["max_supply"],
        "tail_reward": stats["tail_reward"],
        "block_time": stats["block_time"],
        "hashrate_estimate": None if rate is None else round(rate["per_second"], 2),
        "hashrate_window": None if rate is None else {"blocks": rate["blocks"], "seconds": rate["seconds"]},
        "latest_blocks": [
            {
                "height": b["height"],
                "id": b["id"],
                "timestamp": b["timestamp"],
                "weight": b["weight"],
                "tx_count": b["tx_count"],
                "coinbase_total": b["coinbase_total"],
            }
            for b in newest_first[:LATEST]
        ],
    }


def read_node(data_dir, address, now):
    with open(os.path.join(data_dir, "control.cookie")) as f:
        cookie = bytes.fromhex(f.read().strip())
    if len(cookie) != 32:
        raise ProtocolError("the cookie file is not 32 bytes of hex")
    node = Node(address, cookie)
    try:
        info = node.info()
        stats = node.chain_stats()
        tip = stats["height"]
        count = min(MAX_HEADERS, tip + 1)
        blocks = node.headers(tip + 1 - count, count)
    finally:
        node.close()
    return build(info, stats, blocks, now)


def write_atomically(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def main(argv):
    data_dir = os.environ.get("TENERO_DATA", DATA_DIR)
    host, port = os.environ.get("TENERO_CONTROL", "%s:%d" % CONTROL).rsplit(":", 1)
    out = os.environ.get("TENERO_WEB_STATS_OUT", OUT)
    now = int(time.time())
    try:
        result = read_node(data_dir, (host, int(port)), now)
    except (OSError, ProtocolError, ValueError) as e:
        # the reason goes to the journal, not to the public file
        print("no reading: %s" % e, file=sys.stderr)
        result = {"ok": False, "updated": now}
    write_atomically(out, result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
