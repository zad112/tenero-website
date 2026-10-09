// Fills the network panel from stats/stats.json, which tenero-web-stats.sh writes on the server once a minute.
// If the file is missing or old, the page says so instead of showing stale numbers as current.
(function () {
  const STALE_SECONDS = 300;
  const $ = (id) => document.getElementById(id);

  function show(s) {
    const age = Math.floor(Date.now() / 1000) - s.updated;
    $("s-height").textContent = Number(s.height).toLocaleString("en-US");
    $("s-peers").textContent = s.peers;
    $("s-mempool").textContent = s.mempool;
    $("s-sync").textContent = s.syncing ? "syncing" : "in sync";
    const when = new Date(s.updated * 1000).toUTCString();
    $("s-updated").textContent = age > STALE_SECONDS
      ? "Last reading " + when + ": more than 5 minutes old, so the node or the reader may be down."
      : "Last reading " + when + ".";
  }

  function fail() {
    $("s-updated").textContent = "No reading from the node right now.";
  }

  function load() {
    fetch("stats/stats.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((s) => (s && s.ok ? show(s) : fail()))
      .catch(fail);
  }

  load();
  setInterval(load, 60000);
})();
