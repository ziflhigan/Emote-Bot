# Multi-arch Python base (works on x86_64 and arm64 — Pi 5 is arm64).
FROM python:3.12-slim

# Avoid bytecode + buffer stdout/stderr; small image hygiene.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (mounted as a volume in dev, baked in for prod).
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
