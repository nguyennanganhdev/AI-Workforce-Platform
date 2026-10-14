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
  dry-run)
    # Acceptance must use this VPS's network, with no temporary workstation relay.
    unset DUCKDNS_HTTPS_PROXY HTTPS_PROXY HTTP_PROXY ALL_PROXY https_proxy http_proxy all_proxy
    certbot renew --dry-run --non-interactive \
      --config-dir "${TLS_CERT_DIR:-/srv/vinhomes-tls}" \
      --work-dir /srv/vinhomes-certbot-work \
      --logs-dir /srv/vinhomes-certbot-logs
    ;;
  *) echo 'usage: vinhomes-renew-tls [renew|reload|dry-run]' >&2; exit 2 ;;
esac
