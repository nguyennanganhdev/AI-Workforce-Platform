#!/usr/bin/env bash
# Rehearse a backup in isolated containers. Never starts a restored app/model.
set -Eeuo pipefail
umask 077
restore_started=$(date -u +%FT%TZ)
backup=${1:?usage: verify-restore.sh BACKUP_DIRECTORY}
backup=$(cd -- "$backup" && pwd)
if command -v cygpath >/dev/null; then backup=$(cygpath -m "$backup"); export MSYS_NO_PATHCONV=1; fi
[[ -f $backup/COMPLETE ]] || { echo 'Incomplete backup' >&2; exit 1; }
(cd -- "$backup" && sha256sum --check --quiet SHA256SUMS)
if [[ -f $backup/images.tar.gz ]]; then
    gzip -dc "$backup/images.tar.gz" | docker image load >/dev/null
fi
prefix="awp-restorecheck-$(date -u +%Y%m%d%H%M%S)-$RANDOM"
containers=()
volumes=()
cleanup() {
    local code=$?
    trap - EXIT
    for name in "${containers[@]}"; do docker rm -f "$name" >/dev/null 2>&1 || true; done
    for name in "${volumes[@]}"; do docker volume rm "$name" >/dev/null 2>&1 || true; done
    exit "$code"
}
trap cleanup EXIT
helper=$(cat "$backup/app.image-id")
postgres_image=$(cat "$backup/postgres.image-id")
redis_image=$(cat "$backup/redis.image-id")
minio_image=$(cat "$backup/minio.image-id")
for label in postgres redis minio workspaces; do
    volume="$prefix-$label"
    docker volume create "$volume" >/dev/null
    volumes+=("$volume")
    if [[ $label != postgres ]]; then
        docker run --rm -i --pull never --network none --read-only \
            --mount "type=volume,src=$volume,dst=/target" --entrypoint tar \
            "$helper" -C /target -xzf - < "$backup/$label.tar.gz"
    fi
done
containers+=("$prefix-postgres")
docker run -d --pull never --network none --name "$prefix-postgres" \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=restorecheck -e POSTGRES_DB=restorecheck \
    --mount "type=volume,src=$prefix-postgres,dst=/var/lib/postgresql/data" "$postgres_image" >/dev/null
ready=false
for ((i=0;i<90;i++)); do
    if docker exec "$prefix-postgres" pg_isready -U restorecheck -d restorecheck >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
done
[[ $ready == true ]] || { echo 'Restore PostgreSQL did not start' >&2; exit 1; }
docker exec -i "$prefix-postgres" pg_restore -U restorecheck -d restorecheck --exit-on-error --no-owner --no-privileges < "$backup/postgres.dump"
head=$(docker exec "$prefix-postgres" psql -U restorecheck -d restorecheck -Atc 'select version_num from alembic_version')
[[ $head == "$(cat "$backup/migration-head")" ]] || { echo 'Migration mismatch' >&2; exit 1; }
counts=$(docker exec "$prefix-postgres" psql -U restorecheck -d restorecheck -Atc "select json_build_object('users',(select count(*) from auth_users),'workflows',(select count(*) from wf_workflows),'requests',(select count(*) from wf_partner_requests))")
[[ $counts == "$(cat "$backup/database-counts.json")" ]] || { echo 'Database counts differ' >&2; exit 1; }
containers+=("$prefix-redis")
docker run -d --pull never --network none --name "$prefix-redis" \
    --mount "type=volume,src=$prefix-redis,dst=/data" "$redis_image" redis-server --appendonly yes >/dev/null
ready=false
for ((i=0;i<30;i++)); do
    if [[ $(docker exec "$prefix-redis" redis-cli ping 2>/dev/null) == PONG ]]; then ready=true; break; fi
    sleep 1
done
[[ $ready == true ]] || { echo 'Restore Redis did not start' >&2; exit 1; }
if [[ -f $backup/redis-count ]]; then
    [[ $(docker exec "$prefix-redis" redis-cli DBSIZE) == "$(cat "$backup/redis-count")" ]] || { echo 'Redis key counts differ' >&2; exit 1; }
fi
containers+=("$prefix-minio")
docker run -d --pull never --network none --name "$prefix-minio" --env-file "$backup/minio.env" \
    --mount "type=volume,src=$prefix-minio,dst=/data" "$minio_image" server /data >/dev/null
ready=false
for ((i=0;i<45;i++)); do
    if docker exec "$prefix-minio" sh -c 'mc --config-dir /tmp/restore-mc alias set self http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc --config-dir /tmp/restore-mc ready self >/dev/null && mc --config-dir /tmp/restore-mc stat "self/${S3_BUCKET:-agentscope}" >/dev/null' 2>/dev/null; then ready=true; break; fi
    sleep 1
done
[[ $ready == true ]] || { echo 'Restore MinIO did not start or bucket missing' >&2; exit 1; }
if [[ -n ${RESTORE_EVIDENCE:-} ]]; then
    python3 - "$RESTORE_EVIDENCE" "$restore_started" "$head" "${DEPLOY_ENVIRONMENT:-unclassified}" "${SOURCE_REVISION:-unknown}" "$backup" <<'PY'
import datetime,json,os,pathlib,sys
path=pathlib.Path(sys.argv[1]);path.parent.mkdir(parents=True,exist_ok=True)
started=datetime.datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'))
now=datetime.datetime.now(datetime.timezone.utc)
backup=pathlib.Path(sys.argv[6])
release=json.loads((backup/'release.json').read_text()) if (backup/'release.json').is_file() else {}
data={'status':'PASS','scope':'isolated_four_store_restore','environment':sys.argv[4],
      'source_revision':sys.argv[5],'started_at':sys.argv[2],'finished_at':now.isoformat(),
      'source_image_id':(backup/'app.image-id').read_text().strip(),
      'source_manifest_sha256':release.get('source_manifest_sha256'),
      'recovery_images_in_backup':(backup/'images.tar.gz').is_file(),
      'duration_seconds':(now-started).total_seconds(),'migration':sys.argv[3],
      'postgres_counts_match':True,'redis_ready':True,'minio_bucket_ready':True,
      'workspace_archive_recovered':True,'production_cutover_verified':False}
path.write_text(json.dumps(data,indent=2));path.chmod(0o600)
PY
fi
printf 'Restore verification PASS: migration=%s; PostgreSQL counts match; Redis and MinIO ready; all four stores recovered.\n' "$head"
