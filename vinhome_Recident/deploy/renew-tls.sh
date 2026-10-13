#!/bin/sh
# Install as /usr/local/sbin/vinhomes-renew-tls after certificate issuance.
set -eu
case "${1:-renew}" in
  reload)
    docker exec vinhomes-domain-gateway-1 nginx -t
    docker exec vinhomes-domain-gateway-1 nginx -s reload
    ;;
  renew)
    certbot renew --non-interactive \
      --config-dir "${TLS_CERT_DIR:-/srv/vinhomes-tls}" \
      --work-dir /srv/vinhomes-certbot-work \
      --logs-dir /srv/vinhomes-certbot-logs \
      --deploy-hook '/usr/local/sbin/vinhomes-renew-tls reload'
    ;;
  *) echo 'usage: vinhomes-renew-tls [renew|reload]' >&2; exit 2 ;;
esac
