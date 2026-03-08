FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml /app/
COPY apps/cna-worker /app/apps/cna-worker
RUN pip install --no-cache-dir azure-identity azure-storage-blob

CMD ["python", "apps/cna-worker/main.py"]
