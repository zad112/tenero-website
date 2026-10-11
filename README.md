# tenero-website

The website of [Tenero](https://github.com/zad112/Tenero), **teneronetwork.com**: an experimental, unaudited proof-of-work coin (a learning project; nothing on it has any value). The coin's code lives in that repository; this one holds only the site.

Static pages served by **Caddy** on the Contabo server (194.238.27.60), next to the `gamma` seed:

| Path | What |
|---|---|
| `index.html`, `app.js` | the home page: the network panel, the latest blocks, a pool summary, how it works, getting started, thanks |
| `mining/` | the mining guide, with the 1% miner fee and its addresses |
| `pool/` | the test pool's numbers, and a miner's own (below, "The pool page") |
| `faq/`, `roadmap/` | questions; where it stands and what is next |
| `style.css`, `assets/`, `favicon.ico` | shared by every page |
| `deploy/` | the server's files: the Caddyfile, the panel's reader and its timer, the pool-stats transfer |
| `tests/` | the panel reader's tests |

Caddy gets and renews the HTTPS certificate by itself. The pages load nothing from other sites and set no cookies; Caddy's log
keeps no visitor IP addresses. **The pages repeat facts from the coin's [README](https://github.com/zad112/Tenero/blob/main/README.md)**
(the version, the downloads, the seeds, the pool, the fee and its addresses, the warnings): when those change, change them here too.

**The network panel** reads `stats/stats.json`, which `deploy/tenero-web-stats.py` writes once a minute. It asks the seed through
the node's own control protocol (the Tenero repository, `docs/CONTROL_PROTOCOL.md`) for `info`, `chain_stats` and `headers`:
**read requests only, and nothing on the node changes**. It runs as the node's user (`tenero-gamma`), because it needs the control
cookie, and **the web server never sees the cookie** (anything holding it can stop the node), only the JSON. Its service may
reach nothing but this machine. Python's standard library only. If the node is down, or answers something the reader does not
understand (a future protocol change), it writes `{"ok": false}` and the page says "no reading" instead of showing old or wrong
numbers; the reason goes to the journal (`journalctl -u tenero-web-stats`).

What it shows: height, peers, waiting payments, sync state, the difficulty (`2^256 / target`, attempts a block), an **estimated**
hash rate (the work of the last 30 blocks over the time their timestamps say they took, as the block explorer does), coins mined
so far, the block reward, and the latest 20 blocks. The pool card reads `pool-stats/pool.json` (below).

**Tests:** `python -m unittest discover -s tests` checks the reader against the protocol's golden vectors
(`../Tenero/tests/vectors/control.json`, from a Tenero checkout next to this one) and against a stand-in node. Checked on
2026-10-11 against a real `tenerod` too (a test-network node on the PC: the same numbers as `tenerod status`).

**Preview on the PC:** `python -m http.server 8090` in this folder, then <http://localhost:8090>. The panels stay empty without
`stats/stats.json` and `pool-stats/pool.json` (both git-ignored; copy the live ones from the site to see real numbers).

## Putting it on the server (the first time; the owner runs these, one step at a time)

**1. On the PC (PowerShell, in this repository's folder): pack the site and copy it over.**

```powershell
tar -czf $HOME\tenero-web.tgz index.html style.css app.js favicon.ico assets deploy pool mining faq roadmap
scp $HOME\tenero-web.tgz root@194.238.27.60:/root/
```

**2. Check the names point at the server** (both should print `194.238.27.60`; the records are in Contabo's DNS Zone Management):

```bash
getent hosts teneronetwork.com; getent hosts www.teneronetwork.com
```

**3. Install Caddy.** Ubuntu's own package (Caddy 2.6.2 on Ubuntu 24.04, updated with `apt upgrade`). Caddy's own package
repository answered `402 Payment Required` on 2026-10-09, so it was not used.

```bash
apt update && apt install -y caddy
```

**4. Open the web ports** (80 is needed for the certificate and to redirect to HTTPS):

```bash
ufw allow 80/tcp && ufw allow 443/tcp && ufw status
```

**5. Put the files in place, and start the panel's timer:**

```bash
mkdir -p /root/tenero-web && tar -xzf /root/tenero-web.tgz -C /root/tenero-web
mkdir -p /var/www/teneronetwork/stats /opt/tenero-web
cd /root/tenero-web && cp -r index.html style.css app.js favicon.ico assets pool mining faq roadmap /var/www/teneronetwork/ && cd
chown tenero-gamma:tenero-gamma /var/www/teneronetwork/stats
install -m 755 /root/tenero-web/deploy/tenero-web-stats.py /opt/tenero-web/
install -m 644 /root/tenero-web/deploy/tenero-web-stats.service /root/tenero-web/deploy/tenero-web-stats.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now tenero-web-stats.timer
systemctl start tenero-web-stats.service; head -c 300 /var/www/teneronetwork/stats/stats.json; echo
```

The last line should print `{"ok":true,"format":2,...}`. `"ok":false` means the node did not answer: `journalctl -u tenero-web-stats -n 20 --no-pager` says why.

**6. Give Caddy the site:**

```bash
cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.default
install -m 644 /root/tenero-web/deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && systemctl reload caddy
journalctl -u caddy -n 30 --no-pager
```

The log should say `certificate obtained successfully` within a minute. Then open <https://teneronetwork.com>.

## Updating the pages

Repeat step 1, then on the server:

```bash
rm -rf /root/tenero-web && mkdir -p /root/tenero-web && tar -xzf /root/tenero-web.tgz -C /root/tenero-web
cd /root/tenero-web && cp -r index.html style.css app.js favicon.ico assets pool mining faq roadmap /var/www/teneronetwork/ && cd
```

No restart is needed. If `deploy/` changed, install the changed files as in step 5 (and `systemctl daemon-reload` for a changed unit).

### From the shell-script panel to the Python reader (2026-10-11)

The first panel (`tenero-web-stats.sh`, which parsed `tenerod status`) is replaced by `tenero-web-stats.py`. After the update above:

```bash
python3 --version
install -m 755 /root/tenero-web/deploy/tenero-web-stats.py /opt/tenero-web/
install -m 644 /root/tenero-web/deploy/tenero-web-stats.service /etc/systemd/system/
systemctl daemon-reload && systemctl start tenero-web-stats.service; head -c 300 /var/www/teneronetwork/stats/stats.json; echo
rm /opt/tenero-web/tenero-web-stats.sh
```

The timer stays as it is. The home page reads only the new format (`"format":2`): until the reader has run once it says "no reading".

## Licence

BSD 3-Clause, as the coin (`LICENSE`). The logo and banner come from the Tenero repository.

## The pool page (`pool/`, at teneronetwork.com/pool)

The pool runs on the OTHER server (195.26.244.245), which is short of memory, so the page lives here and the pool only writes a
small JSON file every 30 seconds (`tenero-pool`'s `stats-file`, from the release after 0.4.0-gamma.1). A timer on the pool
server sends that file here over SSH, with a key that can do **one thing** on this server: replace that file
(`deploy/receive-pool-stats.sh`). Nothing new listens on the pool server, and nothing here can reach the pool. The file lists
no addresses: each miner is keyed by the SHA-256 of its address, and the page hashes the address a person types, in the browser.

The owner runs these, one block at a time. **A** is the pool server (`ssh root@195.26.244.245`), **W** this one (`ssh root@194.238.27.60`).

**1. W: copy the site's new files over** (from the PC, in this repository's folder, as for the first setup):

```powershell
tar -czf $HOME\tenero-web.tgz index.html style.css app.js favicon.ico assets deploy pool
scp $HOME\tenero-web.tgz root@194.238.27.60:/root/
```

**2. W: the page, the folder the file lands in, and the receiving user** (it may only run the receive script):

```bash
rm -rf /root/tenero-web && mkdir -p /root/tenero-web && tar -xzf /root/tenero-web.tgz -C /root/tenero-web
cp -r /root/tenero-web/index.html /root/tenero-web/pool /var/www/teneronetwork/
useradd --system --create-home --home-dir /var/lib/tenero-pool-stats --shell /bin/sh tenero-pool-stats
mkdir -p /var/www/teneronetwork/pool-stats && chown tenero-pool-stats:tenero-pool-stats /var/www/teneronetwork/pool-stats
install -m 755 /root/tenero-web/deploy/receive-pool-stats.sh /opt/tenero-web/
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

The last line prints this server's host key fingerprint (`SHA256:...`): keep it for step 4.

**3. A: give the pool its stats file, and a key to send it with** (the pool's settings file gets one line; then the pool restarts):

```bash
mkdir -p /var/lib/tenero-gamma-pool/stats /var/lib/tenero-gamma-pool/stats-push
echo "stats-file = /var/lib/tenero-gamma-pool/stats/pool.json" >> /var/lib/tenero-gamma-pool/pool.conf
ssh-keygen -t ed25519 -N "" -C "tenero pool stats push" -f /var/lib/tenero-gamma-pool/stats-push/id_ed25519
chown -R tenero-gamma-pool:tenero-gamma-pool /var/lib/tenero-gamma-pool/stats /var/lib/tenero-gamma-pool/stats-push
systemctl restart tenero-gamma-pool && sleep 40 && head -c 300 /var/lib/tenero-gamma-pool/stats/pool.json; echo
cat /var/lib/tenero-gamma-pool/stats-push/id_ed25519.pub
```

The `head` line must start `{"format":1,"ok":true`. (An older `tenero-pool` refuses the new setting: "unknown setting
`stats-file`". It needs the build with it.) The last line prints the public key, one line starting `ssh-ed25519`: copy it.

**4. A: pin the website server's host key** (so the timer can never be talked into sending to anything else):

```bash
ssh-keyscan -t ed25519 194.238.27.60 > /var/lib/tenero-gamma-pool/stats-push/known_hosts
ssh-keygen -lf /var/lib/tenero-gamma-pool/stats-push/known_hosts
chown tenero-gamma-pool:tenero-gamma-pool /var/lib/tenero-gamma-pool/stats-push/known_hosts
```

The fingerprint printed must be **the same** as the one step 2 printed on W. If it is not, stop.

**5. W: allow that key to run the receive script and nothing else** (paste the key from step 3 in place of `KEY`):

```bash
mkdir -p /var/lib/tenero-pool-stats/.ssh
echo 'restrict,command="/opt/tenero-web/receive-pool-stats.sh" KEY' > /var/lib/tenero-pool-stats/.ssh/authorized_keys
chown -R tenero-pool-stats:tenero-pool-stats /var/lib/tenero-pool-stats/.ssh
chmod 700 /var/lib/tenero-pool-stats/.ssh && chmod 600 /var/lib/tenero-pool-stats/.ssh/authorized_keys
grep -iE "^(AllowUsers|AllowGroups|PasswordAuthentication)" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null
```

If the last line shows an `AllowUsers` line, add `tenero-pool-stats` to it and `systemctl reload ssh`.

**6. A: the timer that sends the file.** First copy the same archive to A, from the PC:

```powershell
scp $HOME\tenero-web.tgz root@195.26.244.245:/root/
```

then on A:

```bash
mkdir -p /root/tenero-web && tar -xzf /root/tenero-web.tgz -C /root/tenero-web
mkdir -p /opt/tenero-web && install -m 755 /root/tenero-web/deploy/push-pool-stats.sh /opt/tenero-web/
install -m 644 /root/tenero-web/deploy/tenero-pool-stats-push.service /root/tenero-web/deploy/tenero-pool-stats-push.timer /etc/systemd/system/
systemctl daemon-reload && systemctl start tenero-pool-stats-push.service && systemctl status tenero-pool-stats-push.service --no-pager | tail -5
systemctl enable --now tenero-pool-stats-push.timer
```

**7. W: the file arrived, and Caddy marks it not to be cached:**

```bash
head -c 200 /var/www/teneronetwork/pool-stats/pool.json; echo
install -m 644 /root/tenero-web/deploy/Caddyfile /etc/caddy/Caddyfile && caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy
```

Then open <https://teneronetwork.com/pool/>. If the page says the numbers are more than 3 minutes old, look at A:
`journalctl -u tenero-pool-stats-push -n 20 --no-pager`.

Preview on the PC: put a `pool-stats/pool.json` in this folder (the format is in the Tenero repository, `docs/RUNNING_A_POOL.md`, "The stats
file") and run `python -m http.server 8090`, then <http://localhost:8090/pool/>.
