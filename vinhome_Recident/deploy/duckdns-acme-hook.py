#!/usr/bin/env python3
"""Certbot manual DNS-01 hook for one DuckDNS name. Root-only token, no IP updates.

Requires dig (Ubuntu package dnsutils). Configure Certbot with this script's auth/cleanup modes.
DuckDNS has one TXT value for all sub-subdomains: do not use simultaneous/wildcard challenges.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import urlopen,build_opener,ProxyHandler


def txt_values(domain):
    result=subprocess.run(['dig','+time=3','+tries=1','+short','TXT','_acme-challenge.'+domain],capture_output=True,text=True,timeout=5)
    if result.returncode:
        raise RuntimeError('DNS lookup failed')
    return [line.strip().strip('"') for line in result.stdout.splitlines() if line.strip().startswith('"') and line.strip().strip('"')]


def update(domain,token,value):
    # DuckDNS's documented TXT endpoint uses HTTPS GET. Never log its URL or exception details.
    query={'domains':domain.removesuffix('.duckdns.org'),'token':token,'txt':value}
    if not value:query['clear']='true'
    try:
        opener=urlopen
        proxy=os.getenv('DUCKDNS_HTTPS_PROXY','')
        if proxy:
            target=urlsplit(proxy)
            if target.scheme!='http' or target.hostname not in ('127.0.0.1','localhost') or not target.port or target.username:
                raise RuntimeError('DNS relay must be a private loopback SSH forward')
            opener=build_opener(ProxyHandler({'https':proxy})).open
        with opener('https://www.duckdns.org/update?'+urlencode(query),timeout=15) as response:
            ok=response.read(128).decode().splitlines()[0]=='OK'
    except Exception:
        raise RuntimeError('DuckDNS update failed; credentials and request URL withheld') from None
    if not ok:raise RuntimeError('DuckDNS rejected the TXT update')


def run(mode,*,sleep=time.sleep):
    domain=os.getenv('CERTBOT_DOMAIN','')
    allowed=os.getenv('DUCKDNS_DOMAIN','vinhome-platform.duckdns.org')
    validation=os.getenv('CERTBOT_VALIDATION','')
    if domain!=allowed or not re.fullmatch(r'[a-z0-9-]+\.duckdns\.org',domain) or not validation:
        raise RuntimeError('Unexpected domain or missing ACME validation')
    token_file=Path(os.getenv('DUCKDNS_TOKEN_FILE','/etc/vinhomes/duckdns-token.secret'))
    if token_file.stat().st_mode & 0o077:
        raise RuntimeError('DuckDNS credential file must be accessible only to its owner (0600)')
    token=token_file.read_text().strip()
    if not token or len(token)>2048 or any(c.isspace() for c in token):
        raise RuntimeError('Invalid DuckDNS credential file')
    current=txt_values(domain)
    if mode=='cleanup':
        # Never clear a TXT record changed by a different process after our challenge.
        if current==[validation]:update(domain,token,'')
        return
    if mode!='auth':raise RuntimeError('Expected auth or cleanup')
    if current and current!=[validation]:
        raise RuntimeError('Existing TXT record belongs to another use; refusing to overwrite it')
    update(domain,token,validation)
    try:
        for _ in range(30):
            if txt_values(domain)==[validation]:return
            sleep(10)
        raise RuntimeError('TXT propagation timed out')
    except Exception:
        if txt_values(domain)==[validation]:update(domain,token,'')
        raise


if __name__=='__main__':
    try:
        run(sys.argv[1] if len(sys.argv)==2 else '')
    except Exception as error:
        # Explicit errors are safe; external libraries' exceptions may contain the credential-bearing URL.
        print(str(error) if type(error) is RuntimeError else 'DNS hook failed; inspect token permissions and DNS tools.',file=sys.stderr)
        raise SystemExit(1)
