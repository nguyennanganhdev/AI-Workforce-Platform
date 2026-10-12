# The backup tool of the deployment: pg_dump of the very database image and mc of the very storage image
# the stack runs, plus one script. Build with this folder as context (compose does).
FROM pgvector/pgvector:pg17
COPY --from=cgr.dev/chainguard/minio:latest /usr/bin/mc /usr/local/bin/mc
COPY --chmod=755 backup.sh /usr/local/bin/backup
ENTRYPOINT ["backup"]
