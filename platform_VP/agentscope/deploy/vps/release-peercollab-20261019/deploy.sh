#!/usr/bin/env bash
# Deploy the direct member collaboration change (app only) as an overlay on
# the running app 28aaf71f (invitefix). Web stays as is. Rolls back on any failed check.
#
# Before the overlay, base.sha256 proves the image's copies of the changed
# files are exactly the base commit's, so only this change is shipped.
set -Eeuo pipefail
umask 077
APP_T=ad34f87a-peercollab-20261019
APP_SHA=ad34f87a2470c8f0220359846f8e8a095630935c
BASE_IMAGE=agentscope-platform:28aaf71f-invitefix-20261019
REL=/opt/awp-platform/releases/peercollab-ad34f87a-20261019
ROOT=/opt/awp-platform/app
BACKUP=/var/backups/awp-platform/peercollab-ad34f87a-20261019
compose=(docker compose -p awp-platform --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" -f "$ROOT/compose.vps.yaml")

exec 8>/var/lock/awp-platform-deploy.lock
flock -n 8 || { echo "another deploy holds the lock" >&2; exit 1; }
cd "$REL"
mkdir -p private

echo "== base image matches the base commit"
[[ $(docker inspect awp-platform-app-1 --format '{{.Config.Image}}') == "$BASE_IMAGE" ]] \
  || { echo "running app is not $BASE_IMAGE" >&2; exit 1; }
# The image was built from a Windows checkout, so some files carry CRLF;
# compare content with CR removed against the base commit's LF blobs.
docker run --rm --entrypoint sh -v "$REL/base.sha256:/tmp/b.sha256:ro" "$BASE_IMAGE" -c '
  cd /app
  while read -r hash path; do
    [ "$(tr -d "\r" < "$path" | sha256sum | cut -c1-64)" = "$hash" ] || { echo "differs: $path"; exit 1; }
  done < /tmp/b.sha256' || { echo "live files differ from base commit" >&2; exit 1; }

echo "== build overlay $APP_T"
(cd overlay && sha256sum -c ../overlay.sha256 >/dev/null)
docker build -q -t agentscope-platform:$APP_T --build-arg VCS_REF=$APP_SHA -f Dockerfile.overlay overlay
docker run --rm --entrypoint sh -v "$REL/overlay.sha256:/tmp/o.sha256:ro" agentscope-platform:$APP_T \
  -c 'cd /app && sha256sum -c /tmp/o.sha256 >/dev/null' || { echo "overlay files differ in image" >&2; exit 1; }
[[ $(docker image inspect agentscope-platform:$APP_T --format '{{index .Config.Labels "org.opencontainers.image.revision"}}') == "$APP_SHA" ]]
docker run --rm --entrypoint python agentscope-platform:$APP_T -c \
  "from agentscope.app.storage._model._team import TeamData, direct_collaboration_enabled; assert direct_collaboration_enabled(TeamData(name='x', direct_member_routing=True))"

echo "== backup"
bash backup-release.sh awp-platform "$BACKUP" > backup.log 2>&1 || { tail -20 backup.log >&2; exit 1; }
tail -3 backup.log

echo "== record current state"
cp "$ROOT/.env" private/env.before
cp "$ROOT/compose.yaml" private/compose.yaml.before
docker inspect awp-platform-app-1 awp-platform-web-1 --format '{{.Name}} {{.Config.Image}} {{.Image}}' > images.before
docker tag "$(docker inspect awp-platform-app-1 --format '{{.Image}}')" "awp-rollback/app:before-peercollab-20261019"
cat images.before

rollback() {
  echo "!! rolling back" >&2
  cp private/env.before "$ROOT/.env"
  cp private/compose.yaml.before "$ROOT/compose.yaml"
  "${compose[@]}" up -d --no-build --no-deps --pull never app
  echo '{"status":"ROLLED_BACK","attempted":"'"$APP_SHA"'"}' > deployment.json
}
trap 'rollback' ERR

echo "== forward the rollback switch to the app"
grep -q 'WORKFORCE_TEAM_COLLABORATION' "$ROOT/compose.yaml" || sed -i -E \
  's#^(\s*)COLLABORATION_MAX_VERIFICATIONS: (.*)$#&\n\1WORKFORCE_TEAM_COLLABORATION: ${WORKFORCE_TEAM_COLLABORATION:-collaborative}#' \
  "$ROOT/compose.yaml"
grep -n 'WORKFORCE_TEAM_COLLABORATION' "$ROOT/compose.yaml"

echo "== switch app image"
sed -i -E "s#^APP_IMAGE=.*#APP_IMAGE=agentscope-platform:$APP_T#" "$ROOT/.env"
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
[[ $(docker exec awp-platform-app-1 printenv WORKFORCE_TEAM_COLLABORATION) == collaborative ]]
docker exec awp-platform-app-1 python -c \
  "from agentscope.app._tool._team_say import _WORKER_DIRECT_INPUT_SCHEMA as s; assert 'handoff' in s['properties']['kind']['enum']"

trap - ERR
echo '{"status":"PASS","app_commit":"'"$APP_SHA"'","app_tag":"'"$APP_T"'","web_image":"'"$(docker inspect awp-platform-web-1 --format '{{.Config.Image}}')"'","backup":"'"$BACKUP"'","model_test_calls":0}' > deployment.json
cat deployment.json
