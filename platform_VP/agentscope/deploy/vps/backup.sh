#!/usr/bin/env bash
# Consistent backup of the unified runtime. Briefly stops application writes.
set -Eeuo pipefail
umask 077
backup_started=$(date -u +%FT%TZ)
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
if command -v cygpath >/dev/null; then root=$(cygpath -m "$root"); export MSYS_NO_PATHCONV=1; fi
project=${1:?usage: backup.sh COMPOSE_PROJECT BACKUP_ROOT}
backup_root=${2:?usage: backup.sh COMPOSE_PROJECT BACKUP_ROOT}
[[ $project =~ ^[a-z0-9][a-z0-9_-]*$ ]] || exit 2
env_file=${ENV_FILE:-$root/.env}
compose=(docker compose --project-name "$project" --env-file "$env_file")
IFS=: read -ra files <<< "${COMPOSE_FILES:-compose.yaml:compose.vps.yaml}"
for file in "${files[@]}"; do compose+=(-f "$root/$file"); done
"${compose[@]}" config --quiet
mkdir -p -- "$backup_root"
backup_root=$(cd -- "$backup_root" && pwd)
exec 9>"$backup_root/.backup.lock"
flock -n 9 || { echo 'Another backup is already running' >&2; exit 1; }
out="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)-$project"
mkdir -- "$out"
chmod 700 "$out"
resume=()
restart() {
    local code=$?
    trap - EXIT
    if ((${#resume[@]})); then
        "${compose[@]}" start "${resume[@]}" >/dev/null || code=1
    fi
    if ((code)); then echo "Backup incomplete: $out" >&2; fi
    exit "$code"
}
trap restart EXIT
for service in app demo-mcp redis minio; do
    id=$("${compose[@]}" ps --status running -q "$service")
    if [[ -n $id ]]; then resume+=("$service"); fi
done
app=$("${compose[@]}" ps -aq app)
[[ -n $app ]] || { echo 'Application container is missing' >&2; exit 1; }
helper=$(docker inspect --format '{{.Image}}' "$app")
for service in app web postgres redis minio; do
    id=$("${compose[@]}" ps -aq "$service")
    [[ -n $id ]] || { echo "Missing service: $service" >&2; exit 1; }
    docker inspect --format '{{.Config.Image}}' "$id" > "$out/$service.image"
    docker inspect --format '{{.Image}}' "$id" > "$out/$service.image-id"
done
# Keep recovery independent of the source VPS and mutable registry tags.
# Reuse a local compressed image bundle while these exact five image IDs match.
if [[ ${INCLUDE_IMAGES:-true} == true ]]; then
    image_set=$(cat "$out/"*.image-id | sort -u | sha256sum | cut -d ' ' -f 1)
    cache="$backup_root/.image-cache"
    mkdir -p -- "$cache"
    chmod 700 "$cache"
    if [[ ! -f $cache/$image_set.tar.gz ]]; then
        mapfile -t image_ids < <(cat "$out/"*.image-id | sort -u)
        docker image save "${image_ids[@]}" | gzip -1 > "$cache/$image_set.part"
        mv -- "$cache/$image_set.part" "$cache/$image_set.tar.gz"
    fi
    ln -- "$cache/$image_set.tar.gz" "$out/images.tar.gz"
fi
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$("${compose[@]}" ps -aq minio)" | grep -E '^MINIO_ROOT_(USER|PASSWORD)=' > "$out/minio.env"
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$app" | grep '^S3_BUCKET=' >> "$out/minio.env"
install -m 600 "$env_file" "$out/runtime.env"
if docker exec "$app" test -f /run/workforce/model-prices.json; then
    docker cp "$app:/run/workforce/model-prices.json" "$out/model-prices.json"
fi
for file in ACCESS.secret.md admin.secret.env; do
    if [[ -f $root/../$file ]]; then install -m 600 "$root/../$file" "$out/$file"; fi
done
for file in "${files[@]}"; do cp -- "$root/$file" "$out/$(basename -- "$file")"; done
if [[ -f $root/release.json ]]; then cp -- "$root/release.json" "$out/release.json"; fi
for file in source-manifest.json web-source-manifest.json ops-manifest.json; do
    if [[ -f $root/$file ]]; then cp -- "$root/$file" "$out/$file"; fi
done
for file in offsite.json monitor.json recipients.txt offsite_known_hosts; do
    if [[ -f /etc/awp-platform/$file ]]; then cp -- "/etc/awp-platform/$file" "$out/host-$file"; fi
done
for file in "$root/deploy/vps/"*.sh "$root/deploy/vps/"*.py "$root/deploy/vps/"*.service "$root/deploy/vps/"*.timer "$root/deploy/vps/P2_RUNBOOK.md" "$root/deploy/vps/operations.example.json"; do
    if [[ -f $file ]]; then cp -- "$file" "$out/ops-$(basename -- "$file")"; fi
done
if [[ -f /etc/nginx/sites-available/awp-platform ]]; then
    cp -- /etc/nginx/sites-available/awp-platform "$out/nginx-platform.conf"
fi
if [[ -d /etc/letsencrypt/live ]]; then
    tar -C /etc -czf "$out/letsencrypt.tar.gz" letsencrypt
fi
"${compose[@]}" stop --timeout 60 app >/dev/null
"${compose[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' < /dev/null > "$out/postgres.dump"
"${compose[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version_num from alembic_version"' < /dev/null > "$out/migration-head"
"${compose[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select json_build_object('\''users'\'',(select count(*) from auth_users),'\''workflows'\'',(select count(*) from wf_workflows),'\''requests'\'',(select count(*) from wf_partner_requests))"' < /dev/null > "$out/database-counts.json"
"${compose[@]}" exec -T redis redis-cli DBSIZE < /dev/null > "$out/redis-count"
if ((${#resume[@]})); then "${compose[@]}" stop --timeout 60 "${resume[@]}" >/dev/null; fi
for spec in 'redis:/data:redis' 'minio:/data:minio' 'app:/app/examples/agent_service/workspaces:workspaces'; do
    IFS=: read -r service destination label <<< "$spec"
    id=$("${compose[@]}" ps -aq "$service")
    volume=$(docker inspect --format "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Name}}{{end}}{{end}}" "$id")
    [[ -n $volume ]] || { echo "Expected named volume for $service:$destination" >&2; exit 1; }
    docker run --rm --pull never --network none --read-only \
        --mount "type=volume,src=$volume,dst=/source,readonly" \
        --entrypoint tar "$helper" -C /source -czf - . > "$out/$label.tar.gz"
done
printf '%s\n' "$project" > "$out/source-project"
date -u +%FT%TZ > "$out/created-at"
python3 - "$out" "$backup_started" "${DEPLOY_ENVIRONMENT:-unclassified}" "${SOURCE_REVISION:-unknown}" <<'PY'
import datetime,json,pathlib,sys
out=pathlib.Path(sys.argv[1])
started=datetime.datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'))
now=datetime.datetime.now(datetime.timezone.utc)
data={'schema_version':1,'environment':sys.argv[3],'source_revision':sys.argv[4],
      'started_at':sys.argv[2],'finished_at':now.isoformat(),'duration_seconds':(now-started).total_seconds(),
      'stores':['postgres','redis','minio','workspaces'],'consistent_app_writes_stopped':True,
      'source_image_id':(out/'app.image-id').read_text().strip(),
      'production_restore_verified':False}
(out/'backup-evidence.json').write_text(json.dumps(data,indent=2))
PY
(cd -- "$out" && sha256sum -- * > SHA256SUMS)
touch "$out/COMPLETE"
echo "Backup complete: $out"
