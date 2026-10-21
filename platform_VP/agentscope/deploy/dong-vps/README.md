# Dong VPS guard (103.238.235.156)

Protection in front of https://vinhome-platform.duckdns.org. The stack itself runs as compose project `awp-dongprod` from `/opt/awp-dong/releases/59dca4cc-20261020`.

| Layer | File | On the server |
|---|---|---|
| Gateway nginx: rate limits, scanner block, timeouts, headers | `gateway.conf` | `/opt/awp-dong/releases/59dca4cc-20261020/gateway.conf` |
| Host firewall: drop by default, allow 22/80/443/8443 | `awp-guard.nft`, `awp-guard-firewall.service` | `/etc/awp-guard/awp-guard.nft`, `/etc/systemd/system/awp-guard-firewall.service` |
| SSH brute-force bans | `fail2ban-awp.conf` | `/etc/fail2ban/jail.d/awp.local` |

## Gateway limits (per client IP; the host and Docker networks are exempt)

| Path | Limit |
|---|---|
| `/api/auth/login`, `/api/auth/register` (and `:8443/auth/...`) | 10 per minute, burst 10 |
| Everything else | 30 per second, burst 100 (the team panel polls every 1.5 s per member) |
| Open connections | 60 |
| `/.env`, `/.git`, `*.php`, `wp-*`, `cgi-bin/`, ... | connection closed (444) |

Requests over the limit get `429`.

## Apply

```bash
# Gateway: test before reload; keep the previous file.
R=/opt/awp-dong/releases/59dca4cc-20261020
cp -p $R/gateway.conf $R/gateway.conf.before-guard
cp gateway.conf $R/gateway.conf
docker exec awp-dongprod-gateway-1 nginx -t && docker exec awp-dongprod-gateway-1 nginx -s reload

# Firewall: schedule an automatic undo first, so a mistake cannot lock SSH out.
systemd-run --on-active=5min --unit=awp-guard-undo nft delete table inet awp_guard
install -D -m 600 awp-guard.nft /etc/awp-guard/awp-guard.nft
install -m 644 awp-guard-firewall.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now awp-guard-firewall
# From a NEW ssh session, confirm login still works, then cancel the undo:
systemctl stop awp-guard-undo.timer

# fail2ban
apt-get install -y fail2ban
install -m 644 fail2ban-awp.conf /etc/fail2ban/jail.d/awp.local
systemctl enable --now fail2ban && fail2ban-client reload
```

Do not enable `nftables.service`: `/etc/nftables.conf` starts with `flush ruleset`.

## Verify

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://vinhome-platform.duckdns.org/api/health   # 200
curl -s -m 5 https://vinhome-platform.duckdns.org/.env; echo "exit=$?"                  # empty reply, exit 52
for i in $(seq 1 15); do curl -s -o /dev/null -w '%{http_code} ' -X POST \
  https://vinhome-platform.duckdns.org/api/auth/login -H 'content-type: application/json' -d '{}'; done
# the first 11 are 4xx from the app, then 429
nft list table inet awp_guard
fail2ban-client status sshd
```

## Roll back

```bash
cp -p $R/gateway.conf.before-guard $R/gateway.conf && docker exec awp-dongprod-gateway-1 nginx -s reload
systemctl disable --now awp-guard-firewall        # deletes table inet awp_guard
systemctl disable --now fail2ban
```

## Not done yet (needs a decision)

- SSH still accepts root passwords; fail2ban only bans repeated failures. Switch to keys only (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`) once everyone who logs in has a key.
- Port 8443 (the API at its root) and the public `/docs` and `/openapi.json` stay open.
- Web scanners are blocked but not banned; a fail2ban jail on gateway logs needs the access log on a host volume.
