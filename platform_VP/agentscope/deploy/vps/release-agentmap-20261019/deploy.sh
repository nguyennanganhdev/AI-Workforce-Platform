#!/usr/bin/env bash
# Deploy web e657fb4b (agent map with character sheets) on top of the
# running leaderfix release. App stays 41813cd1. Rolls back on any failed check.
set -Eeuo pipefail
umask 077
T=e657fb4b-agentmap-20261019
SHA=e657fb4b0278f4aecd8b30857fbcf8c996e5eb6d
REL=/opt/awp-platform/releases/agentmap-e657fb4b-20261019
ROOT=/opt/awp-platform/app
compose=(docker compose -p awp-platform --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" -f "$ROOT/compose.vps.yaml")

exec 8>/var/lock/awp-platform-deploy.lock
flock -n 8 || { echo "another deploy holds the lock" >&2; exit 1; }
cd "$REL"
mkdir -p private

echo "== load image"
docker image inspect agentscope-platform-web:$T >/dev/null 2>&1 || gunzip -c web.tar.gz | docker load
[[ $(docker image inspect agentscope-platform-web:$T --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') == "$SHA" ]] \
  || { echo "revision label mismatch" >&2; exit 1; }

echo "== record current state"
cp "$ROOT/.env" private/env.before
docker inspect awp-platform-app-1 awp-platform-web-1 --format '{{.Name}} {{.Config.Image}} {{.Image}}' > images.before
docker tag "$(docker inspect awp-platform-web-1 --format '{{.Image}}')" "awp-rollback/web:before-agentmap-20261019"
cat images.before

rollback() {
  echo "!! rolling back" >&2
  cp private/env.before "$ROOT/.env"
  "${compose[@]}" up -d --no-build --no-deps --pull never web
  echo '{"status":"ROLLED_BACK","attempted":"'"$SHA"'"}' > deployment.json
}
trap 'rollback' ERR

echo "== switch web image"
sed -i -E "s#^WEB_IMAGE=.*#WEB_IMAGE=agentscope-platform-web:$T#" "$ROOT/.env"
grep -E '^(APP|WEB)_IMAGE=' "$ROOT/.env"
"${compose[@]}" up -d --no-build --no-deps --pull never web

echo "== wait healthy"
for _ in $(seq 90); do
  w=$(docker inspect awp-platform-web-1 --format '{{.State.Health.Status}}')
  [[ $w == healthy ]] && break
  sleep 2
done
[[ $w == healthy ]] || { echo "web not healthy: $w" >&2; false; }

echo "== checks"
for route in / /login /register /workforce/agents /api/health; do
  curl -fsS -o /dev/null "http://127.0.0.1:5173$route"
done
curl -fsS http://127.0.0.1:5173/api/health | grep -q '"ok"'
for route in / /login /workforce/agents /api/health; do
  curl -fsS -o /dev/null "https://vagen-platform.duckdns.org$route"
done
if docker exec awp-platform-web-1 grep -rlq 'Program Files' /usr/share/nginx/html; then echo "bad API base in bundle" >&2; false; fi
# The new map ships the character sheets.
docker exec awp-platform-web-1 sh -c 'ls /usr/share/nginx/html/assets | grep -q coordinator-sprite'

trap - ERR
echo '{"status":"PASS","app_image":"'"$(docker inspect awp-platform-app-1 --format '{{.Config.Image}}')"'","web_commit":"'"$SHA"'","web_tag":"'"$T"'","model_test_calls":0}' > deployment.json
cat deployment.json
