# Dong VPS guard (103.238.235.156)

Protection in front of https://vinhome-platform.duckdns.org. The stack itself runs as compose project `awp-dongprod` from `/opt/awp-dong/releases/59dca4cc-20261020`.

| Layer | File | On the server |
|---|---|---|
| Gateway nginx: rate limits, scanner block, timeouts, headers | `gateway.conf` | `/opt/awp-dong/releases/59dca4cc-20261020/gateway.conf` |
| Host firewall: drop by default, allow 22/80/443 | `awp-guard.nft`, `awp-guard-firewall.service` | `/etc/awp-guard/awp-guard.nft`, `/etc/systemd/system/awp-guard-firewall.service` |
| SSH: keys only for root (two team IPs keep the password) | `sshd-awp-guard.conf` | `/etc/ssh/sshd_config.d/00-awp-guard.conf` |
| Bans: SSH failures, web scanners, rate-limit floods | `fail2ban-awp.conf`, `fail2ban-filter-awp-gw-*.conf` | `/etc/fail2ban/jail.d/awp.local`, `/etc/fail2ban/filter.d/awp-gw-*.conf` |
| Gateway access log for the web jails | `logrotate-awp-gateway` | `/var/log/awp-gateway/access.log`, `/etc/logrotate.d/awp-gateway` |

The release compose file (not in this folder) publishes only `80` and `443` for the gateway and mounts `/var/log/awp-gateway:/var/log/gateway`; port `8443` (the API at its root) was closed on 21/10 because nothing used it.

## Gateway limits (per client IP; the host and Docker networks are exempt)

| Path | Limit |
|---|---|
| `/api/auth/login`, `/api/auth/register` | 10 per minute, burst 10 |
| Everything else | 30 per second, burst 100 (the team panel polls every 1.5 s per member) |
| Open connections | 60 |
| `/.env`, `/.git`, `*.php`, `wp-*`, `cgi-bin/`, ... | connection closed (444); 3 in 10 min bans the IP for 24 h |
| `/api/docs`, `/api/redoc`, `/api/openapi.json` | 404 |

Requests over the limit get `429`; 50 of them in 5 min ban the IP for 1 h.

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

# SSH: schedule an undo, then check from a NEW session with the key before cancelling it.
systemd-run --on-active=5min --unit=awp-sshd-undo sh -c 'rm -f /etc/ssh/sshd_config.d/00-awp-guard.conf; systemctl reload ssh'
install -m 600 sshd-awp-guard.conf /etc/ssh/sshd_config.d/00-awp-guard.conf
sshd -t && systemctl reload ssh
systemctl stop awp-sshd-undo.timer

# fail2ban (the web jails need the gateway log volume above)
apt-get install -y fail2ban
install -d -m 755 /var/log/awp-gateway
install -m 644 logrotate-awp-gateway /etc/logrotate.d/awp-gateway
install -m 644 fail2ban-awp.conf /etc/fail2ban/jail.d/awp.local
install -m 644 fail2ban-filter-awp-gw-probe.conf /etc/fail2ban/filter.d/awp-gw-probe.conf
install -m 644 fail2ban-filter-awp-gw-flood.conf /etc/fail2ban/filter.d/awp-gw-flood.conf
fail2ban-client -t && systemctl enable --now fail2ban && fail2ban-client reload
```

Do not enable `nftables.service`: `/etc/nftables.conf` starts with `flush ruleset`.

## Verify

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://vinhome-platform.duckdns.org/api/health   # 200
curl -s -m 5 https://vinhome-platform.duckdns.org/.env; echo "exit=$?"                  # empty reply, exit 52
for i in $(seq 1 15); do curl -s -o /dev/null -w '%{http_code} ' -X POST \
  https://vinhome-platform.duckdns.org/api/auth/login -H 'content-type: application/json' -d '{}'; done
# the first 11 are 4xx from the app, then 429
curl -s -o /dev/null -w '%{http_code}
' https://vinhome-platform.duckdns.org/api/docs      # 404
sshd -T -C user=root,host=x,addr=203.0.113.9 | grep -E '^(passwordauthentication|permitrootlogin) '   # no / prohibit-password
nft list table inet awp_guard
fail2ban-client status                                  # sshd, awp-gw-probe, awp-gw-flood
```

## Roll back

```bash
cp -p $R/gateway.conf.before-guard $R/gateway.conf && docker exec awp-dongprod-gateway-1 nginx -s reload
systemctl disable --now awp-guard-firewall        # deletes table inet awp_guard
rm /etc/ssh/sshd_config.d/00-awp-guard.conf && systemctl reload ssh
systemctl disable --now fail2ban
# Reopen :8443: restore compose.dongprod.yaml.before-8443 and gateway.conf.before-8443, then `up -d gateway`.
```

## Uptime alerts (not installed yet)

`uptime-check.sh` checks the site and `/api/health` every 2 minutes (`awp-uptime.timer`) and alerts after two failures in a row, then once more when the site is back. Alerts go to the journal (`journalctl -t awp-uptime`) and, if `/etc/awp-guard/uptime.env` sets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, to Telegram.

```bash
install -m 755 uptime-check.sh /usr/local/sbin/awp-uptime-check
install -m 644 awp-uptime.service awp-uptime.timer /etc/systemd/system/
install -m 600 /dev/null /etc/awp-guard/uptime.env   # then add the Telegram token and chat id
systemctl daemon-reload && systemctl enable --now awp-uptime.timer
```

## Still open

- Two team addresses (36.50.135.148, 171.225.203.144) can still sign in as root with the password; give them a key, then delete the `Match` block.
