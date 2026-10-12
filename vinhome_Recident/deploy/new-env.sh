#!/bin/sh
# Writes deploy/deployment.env from deployment.env.example with fresh random secrets. Never replaces an
# existing file: its secrets are the ones the database and the bucket were created with.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
target="$here/deployment.env"
if [ -e "$target" ]; then
  echo "deploy/deployment.env already exists: not replaced." >&2
  exit 1
fi
hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }
umask 077
tr -d '\r' < "$here/deployment.env.example" | while IFS= read -r line; do
  case "$line" in
    POSTGRES_PASSWORD=|API_DB_PASSWORD=|MINIO_ROOT_PASSWORD=|S3_SECRET_KEY=|RESIDENT_SIGNING_KEY=|RECEPTION_DELEGATION_KEY=|RECEPTION_SERVICE_TOKEN=|VINHOMES_API_PLATFORM_MCP_TOKEN=)
      echo "$line$(hex 32)" ;;
    DEMO_PASSWORD=) echo "$line$(hex 8)" ;;
    *) echo "$line" ;;
  esac
done > "$target"
echo "Wrote deploy/deployment.env. Paste OPENAI_API_KEY into it, then:"
echo "  docker compose --env-file deploy/deployment.env -f deploy/compose.yml up -d --build"
