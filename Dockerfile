# ==========================================
# Stage 1: Build & Compile Dependencies
# ==========================================
FROM python:3.11-slim-bullseye AS builder

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Force stdout/stderr streams to be unbuffered to catch errors cleanly
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install essential compilation tools for Python C-extensions (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to the latest secure version
RUN pip install --no-cache-dir --upgrade pip

# Copy only the requirements to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies into a isolated directory prefix
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# Stage 2: Final Secure Runtime Environment
# ==========================================
FROM python:3.11-slim-bullseye AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH

# Create a system group and non-root system user for safety
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/false appuser

WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=builder /root/.local /home/appuser/.local
# Copy application source code
COPY main.py .

# Explicitly hand ownership of the application directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch runtime context away from root
USER appuser

# Expose the application port
EXPOSE 5003

# Configure the container healthcheck to verify runtime availability
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5003/', timeout=3)"]

# Use Uvicorn directly with production optimizations (multiple workers)
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5003", "--workers", "4", "--log-level", "info"]
