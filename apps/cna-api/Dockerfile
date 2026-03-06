FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml /app/
COPY apps/cna-api /app/apps/cna-api
RUN pip install --no-cache-dir fastapi uvicorn pydantic

CMD ["uvicorn", "apps.cna-api.main:app", "--host", "0.0.0.0", "--port", "80"]
