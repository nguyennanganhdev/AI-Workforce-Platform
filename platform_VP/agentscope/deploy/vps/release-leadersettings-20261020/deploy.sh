#!/usr/bin/env bash
# Deploy Leader settings + fairer eval: app overlay on the running
# vinhometest app (df0349b3), and a new web image. Rolls back on any failed check.
#
# base.sha256 proves the running image's copies of the changed files are the
# base commit's (CR stripped: the image was built from a Windows checkout).
set -Eeuo pipefail
umask 077
SHA=9e9a08020b0a57a07148270386600f5363a3d79f
T=9e9a0802-leadersettings-20261020
# The web image was built from 09de9570; the merge after it changed no frontend file.
WEB_SHA=09de95709f4e055b6e83cca2152112a443e186a9
WEB_T=09de9570-leadersettings-20261020
BASE_APP=agentscope-platform:df0349b3-vinhometest-20261020
REL=/opt/awp-platform/releases/leadersettings-09de9570-20261020
ROOT=/opt/awp-platform/app
BACKUP=/var/backups/awp-platform/leadersettings-09de9570-20261020
compose=(docker compose -p awp-platform --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" -f "$ROOT/compose.vps.yaml")

exec 8>/var/lock/awp-platform-deploy.lock
flock -n 8 || { echo "another deploy holds the lock" >&2; exit 1; }
cd "$REL"
mkdir -p private

echo "== running app is the base"
[[ $(docker inspect awp-platform-app-1 --format '{{.Config.Image}}') == "$BASE_APP" ]] \
  || { echo "running app is not $BASE_APP" >&2; exit 1; }
docker run --rm --entrypoint sh -v "$REL/base.sha256:/tmp/b.sha256:ro" "$BASE_APP" -c '
  cd /app
  while read -r hash path; do
    [ "$(tr -d "\r" < "$path" | sha256sum | cut -c1-64)" = "$hash" ] || { echo "differs: $path"; exit 1; }
  done < /tmp/b.sha256' || { echo "live files differ from base commit" >&2; exit 1; }

echo "== load web image"
docker image inspect agentscope-platform-web:$WEB_T >/dev/null 2>&1 || gunzip -c web.tar.gz | docker load
[[ $(docker image inspect agentscope-platform-web:$WEB_T --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') == "$WEB_SHA" ]] \
  || { echo "web revision label mismatch" >&2; exit 1; }

echo "== build app overlay"
(cd overlay && sha256sum -c ../overlay.sha256 >/dev/null)
docker build -q -t agentscope-platform:$T --build-arg VCS_REF=$SHA -f Dockerfile.overlay overlay
docker run --rm --entrypoint sh -v "$REL/overlay.sha256:/tmp/o.sha256:ro" agentscope-platform:$T \
  -c 'cd /app && sha256sum -c /tmp/o.sha256 >/dev/null' || { echo "overlay files differ in image" >&2; exit 1; }
docker run --rm --entrypoint python agentscope-platform:$T -c \
  "from agentscope.app._router._workforce_console import update_leader_settings; from agentscope.app._service._agent_eval import _with_retry"

echo "== backup"
bash backup-release.sh awp-platform "$BACKUP" > backup.log 2>&1 || { tail -20 backup.log >&2; exit 1; }
tail -3 backup.log

echo "== record current state"
cp "$ROOT/.env" private/env.before
docker inspect awp-platform-app-1 awp-platform-web-1 --format '{{.Name}} {{.Config.Image}} {{.Image}}' > images.before
for role in app web; do
  docker tag "$(docker inspect awp-platform-$role-1 --format '{{.Image}}')" "awp-rollback/$role:before-leadersettings-20261020"
done
cat images.before

rollback() {
  echo "!! rolling back" >&2
  cp private/env.before "$ROOT/.env"
  "${compose[@]}" up -d --no-build --no-deps --pull never app web
  echo '{"status":"ROLLED_BACK","attempted":"'"$SHA"'"}' > deployment.json
}
trap 'rollback' ERR

echo "== switch images"
sed -i -E "s#^APP_IMAGE=.*#APP_IMAGE=agentscope-platform:$T#; s#^WEB_IMAGE=.*#WEB_IMAGE=agentscope-platform-web:$WEB_T#" "$ROOT/.env"
grep -E '^(APP|WEB)_IMAGE=' "$ROOT/.env"
"${compose[@]}" up -d --no-build --no-deps --pull never app web

echo "== wait healthy"
for _ in $(seq 120); do
  a=$(docker inspect awp-platform-app-1 --format '{{.State.Health.Status}}')
  w=$(docker inspect awp-platform-web-1 --format '{{.State.Health.Status}}')
  [[ $a == healthy && $w == healthy ]] && break
  sleep 2
done
[[ $a == healthy && $w == healthy ]] || { echo "not healthy: app=$a web=$w" >&2; false; }

echo "== checks"
for route in / /login /register /workforce/leader /api/health; do
  curl -fsS -o /dev/null "http://127.0.0.1:5173$route"
done
curl -fsS http://127.0.0.1:5173/api/health | grep -q '"ok"'
for route in / /login /workforce/leader /api/health; do
  curl -fsS -o /dev/null "https://vagen-platform.duckdns.org$route"
done
# Unauthenticated: the route exists and is protected.
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/api/workforce/console/leader/settings)
[[ $code == 401 ]] || { echo "leader settings route returned $code" >&2; false; }
if docker exec awp-platform-web-1 grep -rlq 'Program Files' /usr/share/nginx/html; then echo "bad API base in bundle" >&2; false; fi
docker exec awp-platform-web-1 sh -c 'grep -rlq "leader/settings" /usr/share/nginx/html/assets'
[[ $(docker exec awp-platform-app-1 printenv WORKFORCE_TEAM_COLLABORATION) == collaborative ]]

trap - ERR
echo '{"status":"PASS","commit":"'"$SHA"'","app_tag":"'"$T"'","web_tag":"'"$WEB_T"'","backup":"'"$BACKUP"'","model_test_calls":0}' > deployment.json
cat deployment.json
