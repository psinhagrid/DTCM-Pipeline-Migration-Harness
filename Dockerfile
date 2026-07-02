# syntax=docker/dockerfile:1
#
# Backend image — FastAPI (uvicorn :8000) + fast-rlm Deno/Pyodide runtime.
# The same image is reused for the litellm service (litellm is in requirements.txt),
# so both share one build.
#
# Base: python:3.12-slim — do NOT bump to 3.13 (polars-runtime-32, fastuuid wheels).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (used by fast-rlm to run the agent loop)
ENV DENO_INSTALL=/root/.deno
ENV PATH="/root/.deno/bin:${PATH}"
RUN curl -fsSL https://deno.land/install.sh | sh

# Deno module + Pyodide cache — bind-mounted as a named volume at runtime
# so packages survive container restarts without re-downloading.
ENV DENO_DIR=/deno-cache
RUN mkdir -p /deno-cache

WORKDIR /app

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY main.py orchestrator.py event_queue.py litellm_config.yaml ./
COPY routes/   ./routes/
COPY agents/   ./agents/
COPY graph/    ./graph/
COPY pipelines/ ./pipelines/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
