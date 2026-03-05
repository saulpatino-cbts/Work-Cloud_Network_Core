FROM python:3.11-slim
LABEL description="CNA Cloud Network Assessment Platform"
WORKDIR /app
RUN apt-get update && apt-get install -y \
    graphviz libcairo2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY . .
ENTRYPOINT ["cna"]
CMD ["--help"]
