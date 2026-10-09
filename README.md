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
