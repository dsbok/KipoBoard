FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# hadolint ignore=DL3018
RUN apk add --no-cache build-base jpeg-dev zlib-dev linux-headers && \
    python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip setuptools wheel && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + && \
    find /opt/venv -type f -name "*.py[co]" -delete

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# hadolint ignore=DL3018
RUN apk add --no-cache jpeg zlib curl && \
    addgroup -S nonroot && adduser -S nonroot -G nonroot

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /opt/venv /opt/venv
COPY --chown=nonroot:nonroot app.py .

USER nonroot:nonroot

EXPOSE 5005

HEALTHCHECK CMD curl --fail http://localhost:5005/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=5005", "--server.address=0.0.0.0", "--server.headless=true"]
