#!/bin/sh
# Backs up the database and the bucket into /backup. See deploy/README.md "Sao lưu và khôi phục".
#
#   backup                  every day at BACKUP_HOUR, for ever (what the compose service runs)
#   backup now              one backup, now
#   backup restore [name]   the newest dump (or the named one) and every file, into an EMPTY database and bucket
#
# /backup/db/vinhomes-<date>-<time>.dump   pg_dump custom format; the newest BACKUP_KEEP are kept
# /backup/files/                           one copy of the bucket, added to on every run. A file deleted in the
#                                          system stays here, so every kept dump still finds the files it names.
set -eu
umask 077

now() { date +%Y-%m-%dT%H:%M:%S%z; }
# S3_USER empty: the files are on an S3 service of your own, which this tool has no administrator key for.
store() { mc --quiet alias set store "$S3_ENDPOINT" "$S3_USER" "$S3_PASSWORD" >/dev/null; }

# One && chain: `set -e` does not stop a function that is called as a condition.
run() {
  started=$(date +%s) && name="vinhomes-$(date +%Y%m%d-%H%M%S).dump" && mkdir -p /backup/db /backup/files &&
  # The database first: every file a row of the dump names is then already in the bucket when the files are copied.
  # Under another name until it is whole, so a dump cut short is never kept as a backup.
  pg_dump --format=custom --dbname="$DATABASE_URL" --file=/backup/db/partial &&
  mv /backup/db/partial "/backup/db/$name" &&
  if [ -n "$S3_USER" ]; then store && mc --quiet mirror --overwrite "store/$S3_BUCKET" /backup/files >/dev/null; fi &&
  ls -1 /backup/db/vinhomes-*.dump | sort -r | tail -n +"$((BACKUP_KEEP + 1))" | xargs -r rm -f &&
  echo "$(now) backup ok: $name $(du -h "/backup/db/$name" | cut -f1), $(ls -1 /backup/db/vinhomes-*.dump | wc -l) dumps kept;" \
       "files $(find /backup/files -type f | wc -l) $(du -sh /backup/files | cut -f1)$([ -n "$S3_USER" ] || echo ' (not copied: S3 service of your own)');" \
       "$(($(date +%s) - started)) s"
}

# /backup/FAILED is what the container's health check looks at.
attempt() {
  if run; then rm -f /backup/FAILED; else
    echo "$(now) backup FAILED: the error is on the lines above" >&2
    touch /backup/FAILED
    return 1
  fi
}

restore() {
  dump=/backup/db/$(basename "${1:-$(ls -1 /backup/db/vinhomes-*.dump | sort | tail -n 1)}")
  echo "$(now) restoring $(basename "$dump")"
  # Rights are not restored: the API's role does not exist yet, and `init` grants them again at the next start.
  pg_restore --exit-on-error --no-acl --dbname="$DATABASE_URL" "$dump"
  if [ -n "$S3_USER" ]; then
    store
    mc --quiet mb --ignore-existing "store/$S3_BUCKET" >/dev/null
    mc --quiet mirror --overwrite /backup/files "store/$S3_BUCKET" >/dev/null
  fi
  echo "$(now) restore ok: $(basename "$dump"), files $(find /backup/files -type f | wc -l)"
}

case "${1:-}" in
  now) attempt ;;
  restore) restore "${2:-}" ;;
  '')
    echo "$(now) a backup every day at ${BACKUP_HOUR}:00 ($TZ), the newest $BACKUP_KEEP dumps kept"
    last=
    while :; do
      # A failed run is tried again five minutes later, until the hour is over.
      if [ "$(date +%-H)" -eq "$BACKUP_HOUR" ] && [ "$(date +%F)" != "$last" ] && attempt; then last=$(date +%F); fi
      sleep 300
    done ;;
  *) echo "usage: backup [now | restore [dump name]]" >&2; exit 2 ;;
esac
