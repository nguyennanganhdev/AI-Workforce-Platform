#!/usr/bin/env bash
# Deploy the "Leader does not poll members" fix (app only) as an overlay on
# the running leadersettings app. Web stays as is. Rolls back on any failed check.
#
# base.sha256 proves the running image's copies of the changed files are the
# base commit's (CR stripped: the image was built from a Windows checkout).
set -Eeuo pipefail
umask 077
SHA=1ee4fe3f2c5940581d19d50c255cc30b11ae0d26
T=1ee4fe3f-noleaderpoll-20261020
BASE_APP=agentscope-platform:9e9a0802-leadersettings-20261020
REL=/opt/awp-platform/releases/noleaderpoll-1ee4fe3f-20261020
ROOT=/opt/awp-platform/app
BACKUP=/var/backups/awp-platform/noleaderpoll-1ee4fe3f-20261020
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

echo "== build app overlay"
(cd overlay && sha256sum -c ../overlay.sha256 >/dev/null)
docker build -q -t agentscope-platform:$T --build-arg VCS_REF=$SHA -f Dockerfile.overlay overlay
docker run --rm --entrypoint sh -v "$REL/overlay.sha256:/tmp/o.sha256:ro" agentscope-platform:$T \
  -c 'cd /app && sha256sum -c /tmp/o.sha256 >/dev/null' || { echo "overlay files differ in image" >&2; exit 1; }
docker run --rm --entrypoint python agentscope-platform:$T -c \
  "from agentscope.app.middleware._peer_leader_middleware import PeerLeaderDispatchMiddleware; import agentscope.app._service._chat"

echo "== backup"
bash backup-release.sh awp-platform "$BACKUP" > backup.log 2>&1 || { tail -20 backup.log >&2; exit 1; }
tail -3 backup.log

echo "== record current state"
cp "$ROOT/.env" private/env.before
docker inspect awp-platform-app-1 awp-platform-web-1 --format '{{.Name}} {{.Config.Image}} {{.Image}}' > images.before
docker tag "$(docker inspect awp-platform-app-1 --format '{{.Image}}')" "awp-rollback/app:before-noleaderpoll-20261020"
cat images.before

rollback() {
  echo "!! rolling back" >&2
  cp private/env.before "$ROOT/.env"
  "${compose[@]}" up -d --no-build --no-deps --pull never app
  echo '{"status":"ROLLED_BACK","attempted":"'"$SHA"'"}' > deployment.json
}
trap 'rollback' ERR

echo "== switch app image"
sed -i -E "s#^APP_IMAGE=.*#APP_IMAGE=agentscope-platform:$T#" "$ROOT/.env"
grep -E '^(APP|WEB)_IMAGE=' "$ROOT/.env"
"${compose[@]}" up -d --no-build --no-deps --pull never app

echo "== wait healthy"
for _ in $(seq 120); do
  a=$(docker inspect awp-platform-app-1 --format '{{.State.Health.Status}}')
  [[ $a == healthy ]] && break
  sleep 2
done
[[ $a == healthy ]] || { echo "app not healthy: $a" >&2; false; }

echo "== checks"
curl -fsS http://127.0.0.1:5173/api/health | grep -q '"ok"'
for route in / /login /workforce/leader /api/health; do
  curl -fsS -o /dev/null "https://vagen-platform.duckdns.org$route"
done
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/api/workforce/console/leader/settings)
[[ $code == 401 ]] || { echo "leader settings route returned $code" >&2; false; }
docker exec awp-platform-app-1 python -c \
  "from agentscope.app.middleware._peer_leader_middleware import PeerLeaderDispatchMiddleware"

trap - ERR
echo '{"status":"PASS","commit":"'"$SHA"'","app_tag":"'"$T"'","web_image":"'"$(docker inspect awp-platform-web-1 --format '{{.Config.Image}}')"'","backup":"'"$BACKUP"'","model_test_calls":0}' > deployment.json
cat deployment.json
