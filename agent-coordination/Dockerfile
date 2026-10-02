FROM python:3.12.3-slim
WORKDIR /coordination
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps --no-build-isolation .
WORKDIR /service
EXPOSE 4300
CMD ["python", "-m", "main"]
