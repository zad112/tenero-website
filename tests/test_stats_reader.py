"""Checks deploy/tenero-web-stats.py against the Tenero repository's control-protocol vectors, and end to end against a
stand-in node on a local socket. Run from this folder:

    python -m unittest discover -s tests

The vectors file is looked for in a Tenero checkout next to this one (../Tenero/tests/vectors/control.json), or at
TENERO_CONTROL_VECTORS.
"""

import importlib.util
import json
import os
import socket
import struct
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stats", os.path.join(HERE, "..", "deploy", "tenero-web-stats.py"))
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)

VECTORS = os.environ.get(
    "TENERO_CONTROL_VECTORS", os.path.join(HERE, "..", "..", "Tenero", "tests", "vectors", "control.json"))
OURS = {"authed", "info", "headers", "chain_stats", "error"}


def load_vectors():
    if not os.path.exists(VECTORS):
        raise unittest.SkipTest("no control.json at " + VECTORS)
    with open(VECTORS, encoding="utf-8") as f:
        return json.load(f)


class AgainstTheVectors(unittest.TestCase):
    def test_every_valid_answer_of_ours_decodes_to_the_vector(self):
        v = load_vectors()
        seen = set()
        for item in v["valid"]:
            m = item["message"]
            if item["direction"] != "response" or m["type"] not in OURS:
                continue
            seen.add(m["type"])
            with self.subTest(note=item["note"]):
                self.assertEqual(stats.decode_response(bytes.fromhex(item["body"])), m)
        self.assertEqual(seen, OURS)

    def test_every_invalid_answer_is_refused(self):
        v = load_vectors()
        n = 0
        for item in v["invalid"]:
            if item["direction"] != "response":
                continue
            n += 1
            with self.subTest(note=item["note"]):
                with self.assertRaises(stats.ProtocolError):
                    stats.decode_response(bytes.fromhex(item["body"]))
        self.assertGreater(n, 100)

    def test_the_requests_we_send_match_the_vectors(self):
        v = load_vectors()
        by_note = {i["note"]: i for i in v["valid"] if i["direction"] == "request"}
        self.assertEqual(stats.frame(bytes([stats.K_CHAIN_STATS])).hex(), by_note["the chain's numbers"]["frame"])
        self.assertEqual(stats.frame(bytes([stats.K_HEADERS]) + struct.pack("<QH", 7, 1)).hex(),
                         by_note["one block summary"]["frame"])
        auth = by_note["authenticate"]
        self.assertEqual(stats.frame(bytes([stats.K_AUTH]) + bytes.fromhex(auth["message"]["cookie"])).hex(), auth["frame"])

    def test_the_limits_are_the_protocols(self):
        lim = load_vectors()["limits"]
        self.assertEqual(stats.MAX_FRAME, lim["max_frame"])
        self.assertEqual(stats.MAX_HEADERS, lim["max_blocks_per_request"])
        self.assertEqual(stats.MAX_NAME, lim["max_name"])
        self.assertEqual(stats.MAX_TEXT, lim["max_text"])


def summary(height, work, timestamp):
    return {"height": height, "cumulative_work": "%064x" % work, "timestamp": timestamp}


class TheEstimates(unittest.TestCase):
    def test_work_over_time(self):
        blocks = [summary(h, 100 * h, 60 * h) for h in range(0, 41)]
        r = stats.estimate_hashrate(blocks, 30)
        self.assertEqual((r["blocks"], r["seconds"]), (30, 1800))
        self.assertAlmostEqual(r["per_second"], 3000 / 1800)
        r = stats.estimate_hashrate(blocks, 1000)
        self.assertEqual(r["blocks"], 39)  # the genesis block is left out

    def test_none_without_two_blocks_or_with_time_going_backwards(self):
        self.assertIsNone(stats.estimate_hashrate([], 30))
        self.assertIsNone(stats.estimate_hashrate([summary(5, 100, 50)], 30))
        self.assertIsNone(stats.estimate_hashrate([summary(1, 100, 50), summary(0, 0, 0)], 30))
        self.assertIsNone(stats.estimate_hashrate([summary(6, 100, 60), summary(5, 100, 60)], 30))
        self.assertIsNone(stats.estimate_hashrate([summary(6, 100, 40), summary(5, 90, 50)], 30))

    def test_difficulty(self):
        self.assertEqual(stats.difficulty("%064x" % (1 << 237)), 1 << 19)
        self.assertIsNone(stats.difficulty("0" * 64))


class FakeNode:
    """Answers like a node: the cookie first, then info, chain_stats and headers from a made-up chain."""

    def __init__(self, cookie, tip=100, refuse=False):
        self.cookie, self.tip, self.refuse = cookie, tip, refuse
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.address = self.server.getsockname()
        self.asked = []
        threading.Thread(target=self.serve, daemon=True).start()

    def send(self, conn, body):
        conn.sendall(struct.pack("<I", len(body)) + body)

    def recv(self, conn):
        head = conn.recv(4)
        if len(head) < 4:
            return None
        (n,) = struct.unpack("<I", head)
        body = b""
        while len(body) < n:
            body += conn.recv(n - len(body))
        return body

    def summary(self, h):
        target = (1 << 237).to_bytes(32, "big")
        work = (h * (1 << 19)).to_bytes(32, "big")
        return (struct.pack("<Q", h) + bytes([h % 256]) * 32 + struct.pack("<Q", 1_800_000_000 + 60 * h) + target + work
                + struct.pack("<QIQ", 1000 * h, h % 3, 2_000_000_000))

    def serve(self):
        conn, _ = self.server.accept()
        with conn:
            body = self.recv(conn)
            if body != bytes([1]) + self.cookie or self.refuse:
                return  # a wrong cookie: closed with no answer, as the node does
            self.send(conn, bytes([0x81]))
            while True:
                body = self.recv(conn)
                if body is None:
                    return
                self.asked.append(body[0])
                if body[0] == 9:
                    net, ver = b"gamma", b"0.4.0-gamma.1"
                    self.send(conn, bytes([0x89]) + struct.pack("<Q", self.tip) + b"\x05" * 32
                              + struct.pack("<IIQI", 3, 1, 0, 2) + b"\x00\x00"
                              + struct.pack("<I", len(net)) + net + struct.pack("<I", len(ver)) + ver)
                elif body[0] == 19:
                    self.send(conn, bytes([0x93]) + struct.pack("<Q", self.tip) + (1 << 237).to_bytes(32, "big")
                              + (self.tip * (1 << 19)).to_bytes(32, "big")
                              + struct.pack("<QQQQQ", 2_000_000_000, self.tip * 2_000_000_000, 2 * 10**15, 50_000_000, 60))
                elif body[0] == 17:
                    start, count = struct.unpack("<QH", body[1:])
                    hs = [h for h in range(start, start + count) if h <= self.tip]
                    self.send(conn, bytes([0x91]) + struct.pack("<I", len(hs)) + b"".join(self.summary(h) for h in hs))
                else:
                    msg = b"unknown"
                    self.send(conn, bytes([0xFF]) + struct.pack("<I", len(msg)) + msg)


class EndToEnd(unittest.TestCase):
    def run_main(self, address, cookie_text):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "control.cookie"), "w") as f:
            f.write(cookie_text)
        out = os.path.join(d, "stats.json")
        os.environ.update(TENERO_DATA=d, TENERO_CONTROL="%s:%d" % address, TENERO_WEB_STATS_OUT=out)
        code = stats.main([])
        with open(out) as f:
            return code, json.load(f)

    def test_a_reading(self):
        cookie = bytes(range(32))
        node = FakeNode(cookie, tip=100)
        code, s = self.run_main(node.address, cookie.hex() + "\n")
        self.assertEqual(code, 0)
        self.assertTrue(s["ok"])
        self.assertEqual((s["network"], s["height"], s["peers"], s["inbound"], s["mempool"], s["syncing"]),
                         ("gamma", 100, 3, 1, 2, False))
        self.assertEqual(s["difficulty"], str(1 << 19))
        self.assertEqual(len(s["latest_blocks"]), 20)
        self.assertEqual(s["latest_blocks"][0]["height"], 100)
        self.assertEqual(s["hashrate_window"], {"blocks": 30, "seconds": 1800})
        self.assertAlmostEqual(s["hashrate_estimate"], (1 << 19) / 60, places=1)
        self.assertEqual(node.asked, [9, 19, 17])  # reads only

    def test_a_chain_of_only_the_genesis_block(self):
        cookie = bytes(32)
        code, s = self.run_main(FakeNode(cookie, tip=0).address, cookie.hex())
        self.assertTrue(s["ok"])
        self.assertEqual(s["latest_blocks"][0]["height"], 0)
        self.assertIsNone(s["hashrate_estimate"])

    def test_a_wrong_cookie_is_no_reading(self):
        code, s = self.run_main(FakeNode(bytes(32), refuse=True).address, bytes(32).hex())
        self.assertEqual(code, 1)
        self.assertEqual(set(s), {"ok", "updated"})

    def test_no_node_is_no_reading(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        address = s.getsockname()
        s.close()
        code, out = self.run_main(address, bytes(32).hex())
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
