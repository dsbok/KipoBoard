# KipoBoard

Simple Pinterest image search proxy.

## Demo

https://kipoboard.daniisaahir.com

## Run Locally

```bash
pip install -r requirements.txt
python3 main.py
```

Open:
http://localhost:5005

## Docker

```bash
docker run -d \
  --name kipoboard \
  --restart unless-stopped \
  -p 5005:5005 \
  ghcr.io/dsbok/kipoboard:latest
```

## Docker Compose

```yaml
services:
  kipoboard:
    image: ghcr.io/dsbok/kipoboard:latest
    restart: unless-stopped
    ports:
      - "5005:5005"
```
