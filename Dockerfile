FROM python:3.11-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim-bullseye AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/false appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY main.py .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5003/', timeout=3)"]

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5003", "--workers", "4", "--log-level", "info"]