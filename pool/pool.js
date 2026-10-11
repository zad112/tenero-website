// The pool page. Reads ../pool-stats/pool.json, which the pool writes every 30 s (`stats-file`) and its server copies here.
// An address typed into the form never leaves the page: it is hashed (SHA-256, in the browser) and the hash is looked up
// in the file, which lists miners only by that hash. Stale or missing numbers are said to be so, not shown as current.
(function () {
  "use strict";
  const STALE_SECONDS = 180;
  const $ = (id) => document.getElementById(id);
  let stats = null;
  let myKey = null;

  function coins(units, upc) {
    const n = Number(units) / (upc || 100000000);
    return n.toLocaleString("en-US", { maximumFractionDigits: n < 1 ? 8 : 4 }) + " TNR";
  }

  function rate(x) {
    const n = Number(x) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(2) + " M/s";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + " k/s";
    return n.toFixed(0) + " /s";
  }

  function utc(t) {
    return new Date(t * 1000).toISOString().replace("T", " ").slice(0, 16);
  }

  function ago(t) {
    const s = Math.max(0, Math.floor(Date.now() / 1000) - t);
    if (s < 90) return s + " s ago";
    if (s < 5400) return Math.round(s / 60) + " min ago";
    return Math.round(s / 3600) + " h ago";
  }

  function showPool(s) {
    const p = s.pool;
    $("p-miners").textContent = p.miners_online;
    $("p-rate").textContent = rate(p.hashrate_estimate);
    $("p-blocks").textContent = Number(p.blocks_in_chain).toLocaleString("en-US");
    $("p-paid").textContent = coins(p.paid_total, s.units_per_coin);
    $("p-key").textContent = s.pool_key;
    const every = Math.round(s.payout_every / 60);
    $("p-terms").textContent =
      "Fee " + s.fee_percent + "% · payouts every " + every + " min to everyone owed at least " +
      coins(s.min_payout, s.units_per_coin) + (s.next_payout ? " · next payout " + utc(s.next_payout) + " UTC" : "") +
      " · " + p.blocks_maturing + " block(s) maturing · " + coins(p.owed_total, s.units_per_coin) + " owed in all" +
      (s.height !== null ? " · chain height " + Number(s.height).toLocaleString("en-US") : "");
    const age = Math.floor(Date.now() / 1000) - s.updated;
    $("p-updated").textContent = age > STALE_SECONDS
      ? "Last numbers " + utc(s.updated) + " UTC: more than 3 minutes old, so the pool, or the copy to this server, may be down."
      : "Numbers from " + utc(s.updated) + " UTC.";

    const rows = $("b-rows");
    rows.textContent = "";
    if (!s.blocks.length) {
      const tr = rows.insertRow();
      const td = tr.insertCell();
      td.colSpan = 4;
      td.className = "muted";
      td.textContent = "None yet.";
    }
    for (const b of s.blocks) {
      const tr = rows.insertRow();
      tr.insertCell().textContent = Number(b.height).toLocaleString("en-US");
      tr.insertCell().textContent = utc(b.time);
      tr.insertCell().textContent = coins(b.reward, s.units_per_coin);
      const st = tr.insertCell();
      st.textContent = b.status;
      st.className = b.status === "in chain" ? "status-in" : "status-other";
    }
  }

  function showMe() {
    $("m-none").hidden = true;
    if (!myKey || !stats) return;
    const m = stats.miners[myKey];
    if (!m) {
      $("me").hidden = true;
      $("m-none").hidden = false;
      return;
    }
    const upc = stats.units_per_coin;
    $("m-online").textContent = m.online ? m.online + (m.online === 1 ? " miner" : " miners") : "no";
    $("m-rate").textContent = rate(m.hashrate_estimate);
    $("m-shares").textContent = m.shares_recent;
    $("m-window").textContent = Number(m.window_percent).toFixed(1) + " %";
    $("m-maturing").textContent = coins(m.maturing, upc);
    $("m-owed").textContent = coins(m.owed, upc);
    $("m-paid").textContent = coins(m.paid, upc);
    $("m-last").textContent = m.last_share
      ? "Last share accepted " + ago(m.last_share) + " (" + utc(m.last_share) + " UTC)."
      : "No share in the last ten minutes.";
    $("me").hidden = false;
  }

  async function hashAddress(a) {
    const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(a));
    return Array.from(new Uint8Array(d), (b) => b.toString(16).padStart(2, "0")).join("");
  }

  $("lookup").addEventListener("submit", async (e) => {
    e.preventDefault();
    const a = $("addr").value.trim();
    $("m-bad").hidden = true;
    if (!/^TENg[1-9A-HJ-NP-Za-km-z]{60,}$/.test(a)) {
      $("me").hidden = true;
      $("m-none").hidden = true;
      $("m-bad").hidden = false;
      return;
    }
    myKey = await hashAddress(a);
    showMe();
  });

  function fail() {
    $("p-updated").textContent = "No numbers from the pool right now.";
  }

  function load() {
    fetch("../pool-stats/pool.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((s) => {
        if (!s || !s.ok || s.format !== 1) return fail();
        stats = s;
        showPool(s);
        showMe();
      })
      .catch(fail);
  }

  load();
  setInterval(load, 30000);
})();
