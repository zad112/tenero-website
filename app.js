// The home page. Fills the network panel and the latest blocks from stats/stats.json, which tenero-web-stats.py writes on
// this server once a minute from the gamma seed, and the pool card from pool-stats/pool.json, which the pool sends every 30 s.
// Missing or old numbers are said to be so, not shown as current.
(function () {
  "use strict";
  const STALE_SECONDS = 300;
  const POOL_STALE_SECONDS = 180;
  const $ = (id) => document.getElementById(id);
  let poolHeights = new Set();
  let lastStats = null;

  const whole = (n) => Number(n).toLocaleString("en-US");

  function coins(units, upc, digits) {
    const n = Number(units) / (upc || 100000000);
    return n.toLocaleString("en-US", { maximumFractionDigits: digits === undefined ? 4 : digits }) + " TNR";
  }

  // 1234567 is "1.23 M": three significant figures and a metric prefix, as the block explorer writes them
  function si(x) {
    const prefixes = ["", "k", "M", "G", "T", "P", "E"];
    let v = Number(x);
    if (!isFinite(v) || v < 0) return "?";
    let i = 0;
    while (v >= 999.5 && i + 1 < prefixes.length) { v /= 1000; i++; }
    const digits = (i === 0 && Number.isInteger(v)) || v >= 99.95 ? 0 : v >= 9.995 ? 1 : 2;
    return v.toFixed(digits) + (prefixes[i] ? " " + prefixes[i] : "");
  }

  function utc(t) {
    return new Date(t * 1000).toISOString().replace("T", " ").slice(0, 16);
  }

  function duration(s) {
    if (s < 90) return Math.round(s) + " s";
    if (s < 5400) return Math.round(s / 60) + " min";
    return (s / 3600).toFixed(1) + " h";
  }

  function showStats(s) {
    lastStats = s;
    const upc = s.units_per_coin;
    $("s-height").textContent = whole(s.height);
    $("s-peers").textContent = s.peers;
    $("s-mempool").textContent = s.mempool;
    $("s-sync").textContent = s.syncing ? "syncing" : "in sync";
    // the difficulty is text in the file: it can pass what a JavaScript number holds exactly
    $("s-diff").textContent = si(Number(s.difficulty));
    $("s-rate").textContent = s.hashrate_estimate === null ? "–" : si(s.hashrate_estimate) + "/s";
    const share = (100 * s.emitted) / s.max_supply;
    $("s-emitted").textContent = coins(s.emitted, upc, 0);
    $("s-reward").textContent = coins(s.next_reward, upc);

    const age = Math.floor(Date.now() / 1000) - s.updated;
    $("s-updated").textContent = (age > STALE_SECONDS
      ? "Last reading " + utc(s.updated) + " UTC: more than 5 minutes old, so the node or the reader may be down."
      : "Last reading " + utc(s.updated) + " UTC.") + (s.version ? " The seed runs " + s.version + "." : "");
    const w = s.hashrate_window;
    $("s-rate-note").textContent =
      (w
        ? "The hash rate is an ESTIMATE: the work of the last " + w.blocks + " blocks over the " + duration(w.seconds) +
          " their timestamps say they took (" + duration(w.seconds / w.blocks) + " a block on average; 60 s is the aim). " +
          "Nobody can measure it. "
        : "") +
      "Mined so far is " + share.toFixed(3) + "% of the 20,000,000 main supply.";
    showBlocks(s);
  }

  function showBlocks(s) {
    const rows = $("s-blocks");
    rows.textContent = "";
    for (const b of s.latest_blocks || []) {
      const tr = rows.insertRow();
      const h = tr.insertCell();
      h.textContent = whole(b.height);
      if (poolHeights.has(b.height)) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = "pool";
        h.append(" ", tag);
      }
      tr.insertCell().textContent = b.height === 0 ? "the launch" : utc(b.timestamp);
      tr.insertCell().textContent = b.tx_count;
      tr.insertCell().textContent = b.weight ? whole(b.weight) : "–";
      tr.insertCell().textContent = b.height === 0 ? "–" : coins(b.coinbase_total, s.units_per_coin);
    }
    if (!rows.rows.length) {
      const td = rows.insertRow().insertCell();
      td.colSpan = 5;
      td.className = "muted";
      td.textContent = "No blocks in the reading.";
    }
  }

  function noStats() {
    $("s-updated").textContent = "No reading from the node right now.";
    $("s-rate-note").textContent = "";
  }

  function showPool(p) {
    const n = p.pool;
    $("ps-miners").textContent = n.miners_online;
    $("ps-rate").textContent = si(n.hashrate_estimate) + "/s";
    $("ps-blocks").textContent = whole(n.blocks_in_chain);
    $("ps-next").textContent = p.next_payout ? utc(p.next_payout) + " UTC" : "–";
    const age = Math.floor(Date.now() / 1000) - p.updated;
    $("ps-updated").textContent = age > POOL_STALE_SECONDS
      ? "More than 3 minutes old: the pool, or the copy to this server, may be down."
      : "Numbers from " + utc(p.updated) + " UTC. Hash rates are estimates.";
    poolHeights = new Set((p.blocks || []).filter((b) => b.status === "in chain").map((b) => b.height));
    if (lastStats) showBlocks(lastStats);
  }

  function noPool() {
    $("ps-updated").textContent = "No numbers from the pool right now.";
  }

  function get(url) {
    return fetch(url, { cache: "no-store" }).then((r) => (r.ok ? r.json() : Promise.reject()));
  }

  function load() {
    get("stats/stats.json").then((s) => (s && s.ok && s.format === 2 ? showStats(s) : noStats())).catch(noStats);
    get("pool-stats/pool.json").then((p) => (p && p.ok && p.pool ? showPool(p) : noPool())).catch(noPool);
  }

  load();
  setInterval(load, 60000);
})();
