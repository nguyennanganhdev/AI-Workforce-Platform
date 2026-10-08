FROM python:3.12-slim
WORKDIR /opt/reception
COPY agent-reception/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home app \
    && mkdir -p /var/lib/reception && chown app:app /var/lib/reception
COPY agent-reception/src ./src
USER app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 RECEPTION_STATE_PATH=/var/lib/reception/reception.sqlite3
EXPOSE 4202
CMD ["python", "-m", "uvicorn", "src.runtime.service:create_app", "--factory", "--host", "0.0.0.0", "--port", "4202"]
