# dinterest

Simple Pinterest image search proxy written in Python.

## Instance

https://dinterest.daniisaahir.com

## Run with Python

```bash
pip install -r requirements.txt
python3 main.py
```

Runs on:
http://localhost:5003

## Docker Run

```bash
docker run -d --name dinterest --restart unless-stopped -p 5003:5003 ghcr.io/dsbok/dinterest:latest
```

## Docker Compose

```yaml
services:
  dinterest:
    image: ghcr.io/dsbok/dinterest:latest
    container_name: dinterest
    restart: unless-stopped
    ports:
      - "5003:5003"
```
