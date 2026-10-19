#!/usr/bin/env bash
# Deploy app+web 0321c727 (PR #108). Backup first; roll back on any failed check.
set -Eeuo pipefail
umask 077
T=0321c727-leaderfix-20261019
SHA=0321c727b3b115cf635b2b9ba1bdcfcba0b4c5dd
APP_T=41813cd1-leaderfix-20261019
APP_SHA=41813cd18da5738b0b26a23c197cc411a7513e70
REL=/opt/awp-platform/releases/leaderfix-0321c727-20261019
ROOT=/opt/awp-platform/app
BACKUP=/var/backups/awp-platform/leaderfix-0321c727-20261019
compose=(docker compose -p awp-platform --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" -f "$ROOT/compose.vps.yaml")

exec 8>/var/lock/awp-platform-deploy.lock
flock -n 8 || { echo "another deploy holds the lock" >&2; exit 1; }
cd "$REL"
mkdir -p private

echo "== load images"
docker image inspect agentscope-platform:$T >/dev/null 2>&1 || gunzip -c images.tar.gz | docker load
for image in agentscope-platform:$T agentscope-platform-web:$T; do
  [[ $(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') == "$SHA" ]] \
    || { echo "revision label mismatch: $image" >&2; exit 1; }
done

echo "== backend overlay $APP_T"
(cd overlay && sha256sum -c ../overlay.sha256 >/dev/null)
docker build -q -t agentscope-platform:$APP_T --build-arg VCS_REF=$APP_SHA overlay
docker run --rm --entrypoint sh -v "$REL/overlay.sha256:/tmp/o.sha256:ro" agentscope-platform:$APP_T \
  -c 'cd /app && sha256sum -c /tmp/o.sha256 >/dev/null' || { echo "overlay files differ in image" >&2; exit 1; }
[[ $(docker image inspect agentscope-platform:$APP_T --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') == "$APP_SHA" ]]

echo "== backup"
bash backup-release.sh awp-platform "$BACKUP" > backup.log 2>&1 || { tail -20 backup.log >&2; exit 1; }
tail -3 backup.log

echo "== record current state"
cp "$ROOT/.env" private/env.before
cp "$ROOT/compose.yaml" private/compose.yaml.before
cp "$ROOT/compose.vps.yaml" private/compose.vps.yaml.before
docker inspect awp-platform-app-1 awp-platform-web-1 --format '{{.Name}} {{.Config.Image}} {{.Image}}' > images.before
for role in app web; do
  docker tag "$(docker inspect awp-platform-$role-1 --format '{{.Image}}')" "awp-rollback/$role:before-leaderfix-20261019"
done

rollback() {
  echo "!! rolling back" >&2
  cp private/env.before "$ROOT/.env"
  "${compose[@]}" up -d --no-build --no-deps --pull never app web
  echo '{"status":"ROLLED_BACK","attempted":"'"$SHA"'"}' > deployment.json
}
trap 'rollback' ERR

echo "== switch images"
sed -i -E "s#^APP_IMAGE=.*#APP_IMAGE=agentscope-platform:$APP_T#; s#^WEB_IMAGE=.*#WEB_IMAGE=agentscope-platform-web:$T#" "$ROOT/.env"
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
for route in / /login /register /api/health; do
  curl -fsS -o /dev/null "http://127.0.0.1:5173$route"
done
curl -fsS http://127.0.0.1:5173/api/health | grep -q '"ok"'
for route in / /login /workforce/leader /credential /api/health; do
  curl -fsS -o /dev/null "https://vagen-platform.duckdns.org$route"
done
if docker exec awp-platform-web-1 grep -rlq 'Program Files' /usr/share/nginx/html; then echo "bad API base in bundle" >&2; false; fi
docker exec awp-platform-app-1 python -c "import agentscope.app.vin_platform._egress, agentscope.app._service._catalog_resources as c; assert hasattr(c, 'is_operator')"

trap - ERR
echo '{"status":"PASS","app_commit":"'"$APP_SHA"'","app_tag":"'"$APP_T"'","web_commit":"'"$SHA"'","web_tag":"'"$T"'","backup":"'"$BACKUP"'","model_test_calls":0}' > deployment.json
cat deployment.json
