FROM python:3.12-slim
WORKDIR /opt/vinhomes-api
COPY services/vinhomes-api/pyproject.toml ./
COPY services/vinhomes-api/src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home app
USER app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 VINHOMES_API_HOST=0.0.0.0 VINHOMES_API_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "vinhomes_api"]
