"""Render TLS from the same gateway routes used by HTTP; no second proxy or Caddy."""
import argparse
import re
from pathlib import Path


def render(domain: str) -> str:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", domain) or '..' in domain or '.' not in domain:
        raise ValueError('A DNS hostname is required')
    base = (Path(__file__).parent/'nginx/gateway.conf.template').read_text(encoding='utf-8')
    assert base.count('  listen 8080;') == 1
    tls = base.replace('  listen 8080;', f'''  listen 8443 ssl;
  server_name {domain};
  ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_session_cache shared:TLS:10m;
  add_header Referrer-Policy same-origin always;''', 1)
    http = f'''server {{
  listen 8080;
  server_name {domain};
  location = /healthz {{ return 200 "ok\\n"; }}
  location ^~ /.well-known/acme-challenge/ {{
    root /var/www/acme;
    default_type text/plain;
    try_files $uri =404;
  }}
  location / {{ return 308 https://{domain}$request_uri; }}
}}
'''
    # A distinct container port keeps the SSH-only MCP endpoint usable without making public HTTP an exception
    # to TLS. Publish this listener only on 127.0.0.1; never decide privacy from a spoofable Host header.
    private = base.replace('  listen 8080;', '  listen 8081;', 1)
    return http + tls + private


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain',required=True)
    args=parser.parse_args()
    output=Path(__file__).parent/'nginx/gateway.tls.generated.conf.template'
    output.write_text(render(args.domain),encoding='utf-8')
    print('TLS gateway rendered; enable compose.tls.yml only after certificate issuance.')
