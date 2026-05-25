# KipoBoard

Simple Pinterest image search proxy built with Python.

## Demo

https://kipoboard.daniisaahir.com

## Run Locally

```bash
pip install -r requirements.txt
python3 main.py
```

Open:
http://localhost:5003

## Docker

```bash
docker run -d \
  --name kipoboard \
  --restart unless-stopped \
  -p 5003:5003 \
  ghcr.io/dsbok/KipoBoard:latest
```

## Docker Compose

```yaml
services:
  kipoboard:
    image: ghcr.io/dsbok/KipoBoard:latest
    restart: unless-stopped
    ports:
      - "5003:5003"
```
