# Build with the service folder as context:  docker build -t vinhomes-api services/vinhomes-api
FROM python:3.12-slim
WORKDIR /opt/vinhomes-api
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app \
    && mkdir -p /var/lib/vinhomes/files && chown app /var/lib/vinhomes/files
USER app
# Uploaded photos live here; the deployment mounts a volume over it.
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 VINHOMES_API_HOST=0.0.0.0 VINHOMES_API_PORT=8000 \
    VINHOMES_RESIDENT_FILE_ROOT=/var/lib/vinhomes/files
EXPOSE 8000
CMD ["python", "-m", "vinhomes_api"]
