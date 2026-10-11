# tenero-website

The website of [Tenero](https://github.com/zad112/Tenero), **teneronetwork.com**: an experimental, unaudited proof-of-work coin (a learning project; nothing on it has any value). The coin's code lives in that repository; this one holds only the site.

A static page (`index.html`, `style.css`, `app.js`, `assets/`) served by **Caddy** on the Contabo server (194.238.27.60), next to the
`gamma` seed. Caddy gets and renews the HTTPS certificate by itself. The page loads nothing from other sites and sets no cookies;
Caddy's log keeps no visitor IP addresses.

**The network panel** reads `stats/stats.json`, which `deploy/tenero-web-stats.sh` writes once a minute from `tenerod status`.
That script runs as the node's user (`tenero-gamma`), because it needs the control cookie; **the web server never sees the cookie**
(anything holding it can stop the node), only the JSON. If the node is down the page says "no reading" instead of old numbers.

Preview on the PC: `python -m http.server 8090` in this folder, then <http://localhost:8090> (the panel stays empty without a `stats/stats.json`).

## Putting it on the server (the owner runs these; one step at a time)

**0. Wait for the RAM upgrade to finish**, then check that the seed is up:

```bash
free -h
systemctl status tenero-gamma --no-pager
```

**1. On the PC (PowerShell, in this repository's folder): pack the site and copy it over.**

```powershell
tar -czf $HOME\tenero-web.tgz index.html style.css app.js favicon.ico assets deploy
scp $HOME\tenero-web.tgz root@194.238.27.60:/root/
```

**2. Check the names point at the server** (both should print `194.238.27.60`; if `www` prints nothing, delete
`, www.teneronetwork.com` from the Caddyfile in step 6, or Caddy will keep failing to get a certificate for it):

```bash
getent hosts teneronetwork.com; getent hosts www.teneronetwork.com
```

**3. Install Caddy from Caddy's own package repository** (Caddy's documented steps for Ubuntu; it then updates with `apt upgrade`):

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
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
cp -r /root/tenero-web/index.html /root/tenero-web/style.css /root/tenero-web/app.js /root/tenero-web/favicon.ico /root/tenero-web/assets /var/www/teneronetwork/
chown tenero-gamma:tenero-gamma /var/www/teneronetwork/stats
install -m 755 /root/tenero-web/deploy/tenero-web-stats.sh /opt/tenero-web/
install -m 644 /root/tenero-web/deploy/tenero-web-stats.service /root/tenero-web/deploy/tenero-web-stats.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now tenero-web-stats.timer
systemctl start tenero-web-stats.service && cat /var/www/teneronetwork/stats/stats.json
```

The last line should print `{"ok":true,"network":"gamma","height":...}`. `"ok":false` means `tenerod status` failed: try it by hand
(`/opt/tenero-gamma/tenerod status --data /var/lib/tenero-gamma/data --control 127.0.0.1:38352`).

**6. Give Caddy the site:**

```bash
cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.default
install -m 644 /root/tenero-web/deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy
journalctl -u caddy -n 30 --no-pager
```

The log should say `certificate obtained successfully` within a minute. Then open <https://teneronetwork.com>.

## Updating the page

Repeat step 1, then on the server:

```bash
rm -rf /root/tenero-web && mkdir -p /root/tenero-web && tar -xzf /root/tenero-web.tgz -C /root/tenero-web
cp -r /root/tenero-web/index.html /root/tenero-web/style.css /root/tenero-web/app.js /root/tenero-web/favicon.ico /root/tenero-web/assets /var/www/teneronetwork/
```

No restart is needed. **Keep the page's facts in step with the coin's [README](https://github.com/zad112/Tenero/blob/main/README.md)** (version, seeds, pool, warnings): it is a second copy of them.

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
