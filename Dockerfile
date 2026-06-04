FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir flask requests gunicorn

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN addgroup -S nonroot && adduser -S nonroot -G nonroot

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY main.py .

RUN chown -R nonroot:nonroot /app

USER nonroot:nonroot

EXPOSE 5005

CMD ["gunicorn", "--workers", "5", "--bind", "0.0.0.0:5005", "main:app"]
