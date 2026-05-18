# --- Stage 1: Build and dependency installation ---
FROM python:3.11-alpine AS builder

WORKDIR /app

# Install build dependencies if any packages require compilation
RUN apk add --no-cache gcc musl-dev libffi-dev

# Install python dependencies straight into a local directory
RUN pip install --no-cache-dir --user fastapi uvicorn httpx jinja2 pydantic

# --- Stage 2: Final lightweight runtime ---
FROM gcr.io/distroless/python3-debian12:latest

WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /root/.local /root/.local
# Copy your application source code
COPY main.py .

# Update environment path to look for the copied packages
ENV PYTHONPATH=/root/.local/lib/python3.11/site-packages
ENV PYTHONUNBUFFERED=1

EXPOSE 5003

# Distroless has no shell, so CMD must use the JSON array syntax
CMD ["/usr/bin/python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5003"]
