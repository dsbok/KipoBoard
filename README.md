# dinterest

Simple Pinterest image search proxy built with Python.

## Demo

https://dinterest.daniisaahir.com

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
  --name dinterest \
  --restart unless-stopped \
  -p 5003:5003 \
  ghcr.io/dsbok/dinterest:latest
```

## Docker Compose

```yaml
services:
  dinterest:
    image: ghcr.io/dsbok/dinterest:latest
    restart: unless-stopped
    ports:
      - "5003:5003"
```
