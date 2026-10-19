#!/usr/bin/env bash
# Run on the Platform VPS from an uploaded, tested release directory.
set -Eeuo pipefail
umask 077

if [[ $# -ne 1 ]]; then
    echo "Usage: bash deploy/deploy.sh vagents-landing:<release>" >&2
    exit 2
fi
if [[ $(id -u) -ne 0 ]]; then
    echo "Run as root to update the existing host nginx configuration." >&2
    exit 2
fi

release_image=$1
release_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
nginx_config=/etc/nginx/sites-available/awp-platform
domain=vagen-platform.duckdns.org
project=vagents-landing
backup_dir=/var/backups/vagents-landing
mkdir -p "$backup_dir"
exec 9>"$backup_dir/deploy.lock"
flock -n 9 || { echo "Another landing deployment is running." >&2; exit 1; }

docker image inspect "$release_image" >/dev/null
nginx -t
previous_container=$(docker ps -aq --filter "label=com.docker.compose.project=$project" --filter label=com.docker.compose.service=landing)
previous_image=
if [[ -n $previous_container ]]; then
    [[ $(wc -w <<<"$previous_container") -eq 1 ]]
    previous_image=$(docker inspect --format '{{.Config.Image}}' "$previous_container")
fi
backup="$backup_dir/nginx-$(date -u +%Y%m%dT%H%M%SZ)-$$.conf"
cp --preserve=mode,ownership "$nginx_config" "$backup"
original_nginx_hash=$(sha256sum "$nginx_config" | cut -d ' ' -f 1)
platform_containers=$(docker ps -q --filter label=com.docker.compose.project=awp-platform | sort)
config_changed=0
applied_nginx_hash=
container_changed=0

compose_up() {
    LANDING_IMAGE="$1" docker compose -p "$project" -f "$release_dir/compose.yaml" up -d --no-build --pull never
}

rollback() {
    result=$?
    [[ $result -ne 0 ]] || result=1
    trap - EXIT INT TERM HUP
    # Continue restoring the container even if restoring nginx reports a failure.
    set +e
    echo "Landing deployment failed; restoring previous landing and nginx." >&2
    if [[ $config_changed -eq 1 ]]; then
        current_nginx_hash=$(sha256sum "$nginx_config" | cut -d ' ' -f 1)
        if [[ $current_nginx_hash == "$applied_nginx_hash" ]]; then
            cp --preserve=mode,ownership "$backup" "$nginx_config.rollback"
            mv -f -- "$nginx_config.rollback" "$nginx_config"
            nginx -t && systemctl reload nginx
        else
            echo "Host nginx changed concurrently; preserved that newer configuration." >&2
        fi
    fi
    if [[ $container_changed -eq 1 ]]; then
        if [[ -n $previous_image ]]; then
            compose_up "$previous_image"
        else
            LANDING_IMAGE="$release_image" docker compose -p "$project" -f "$release_dir/compose.yaml" down
        fi
    fi
    exit "${result:-1}"
}
trap rollback EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

container_changed=1
compose_up "$release_image"
healthy=0
for attempt in {1..30}; do
    if curl --fail --silent --max-time 3 http://127.0.0.1:5180/ >/dev/null; then
        healthy=1
        break
    fi
    sleep 1
done
[[ $healthy -eq 1 ]]
homepage=$(curl --fail --silent --show-error --max-time 5 http://127.0.0.1:5180/)
runtime_path=$(python3 -c 'import re, sys; print(re.search(r"src=\"(/landing-assets/build/[^\"]+\.js)\"", sys.stdin.read()).group(1))' <<<"$homepage")
curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:5180$runtime_path" >/dev/null
[[ $(docker ps -q --filter label=com.docker.compose.project=awp-platform | sort) == "$platform_containers" ]]

# Only add managed locations inside the known Platform TLS server. Existing
# application routes, TLS, partner paths and the S3 server remain as they are.
applied_nginx_hash=$(python3 - "$nginx_config" "$release_dir/deploy/nginx-locations.conf" "$original_nginx_hash" <<'PY'
from pathlib import Path
import hashlib
import os
import sys

target, snippet = map(Path, sys.argv[1:3])
content = target.read_text()
original = content
if hashlib.sha256(target.read_bytes()).hexdigest() != sys.argv[3]:
    raise SystemExit("Host nginx changed concurrently; retry from a fresh snapshot")
begin = "    # BEGIN VAGENTS LANDING\n"
end = "    # END VAGENTS LANDING\n"
if content.count(begin) != content.count(end) or content.count(begin) > 1:
    raise SystemExit("Refusing to edit inconsistent landing nginx markers")
if begin in content:
    start = content.index(begin)
    stop = content.index(end, start) + len(end)
    content = content[:start] + content[stop:]
anchor = "    location = /health {\n"
if content.count(anchor) != 1:
    raise SystemExit("Expected one known Platform /health location; review nginx manually")
server_start = content.rfind("server {", 0, content.index(anchor))
server_header = content[server_start:content.index(anchor)]
if "server_name vagen-platform.duckdns.org;" not in server_header or "listen 443 ssl;" not in server_header:
    raise SystemExit("Platform TLS server does not match the audited configuration")
updated = content.replace(anchor, snippet.read_text().rstrip() + "\n" + anchor, 1)
if updated == original:
    print("unchanged")
    raise SystemExit(0)
temporary = target.with_name(target.name + ".landing-new")
temporary.write_text(updated)
os.chmod(temporary, target.stat().st_mode)
os.chown(temporary, target.stat().st_uid, target.stat().st_gid)
os.replace(temporary, target)
print(hashlib.sha256(target.read_bytes()).hexdigest())
PY
)
if [[ $applied_nginx_hash != unchanged ]]; then
    config_changed=1
    nginx -t
    systemctl reload nginx
fi

for route in / /login /workforce/leader /api/health; do
    curl --fail --silent --show-error --max-time 15 \
        --resolve "$domain:443:127.0.0.1" "https://$domain$route" >/dev/null
done
[[ $(docker ps -q --filter label=com.docker.compose.project=awp-platform | sort) == "$platform_containers" ]]
trap - EXIT INT TERM HUP
printf 'Landing deployed: %s\nNginx backup: %s\nPrevious landing image: %s\n' "$release_image" "$backup" "${previous_image:-none}"
