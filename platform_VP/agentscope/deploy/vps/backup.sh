#!/usr/bin/env bash
# Consistent backup of the unified runtime. Briefly stops application writes.
set -Eeuo pipefail
umask 077
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
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$("${compose[@]}" ps -aq minio)" | grep -E '^MINIO_ROOT_(USER|PASSWORD)=' > "$out/minio.env"
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$app" | grep '^S3_BUCKET=' >> "$out/minio.env"
install -m 600 "$env_file" "$out/runtime.env"
for file in ACCESS.secret.md admin.secret.env; do
    if [[ -f $root/../$file ]]; then install -m 600 "$root/../$file" "$out/$file"; fi
done
for file in "${files[@]}"; do cp -- "$root/$file" "$out/$(basename -- "$file")"; done
if [[ -f $root/release.json ]]; then cp -- "$root/release.json" "$out/release.json"; fi
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
(cd -- "$out" && sha256sum -- * > SHA256SUMS)
touch "$out/COMPLETE"
echo "Backup complete: $out"
