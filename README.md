# KipoBoard

Simple Pinterest image search proxy.

## Demo

https://kipoboard.daniisaahir.com

## Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
gunicorn --workers 2 --bind 0.0.0.0:5005 app:app
```

Open:
http://localhost:5005

## Docker

```bash
docker run -d \
  --name kipoboard \
  --restart unless-stopped \
  -p 5005:5005 \
  ghcr.io/dsbok/kipoboard:main
```

## Docker Compose

```yaml
services:
  kipoboard:
    image: ghcr.io/dsbok/kipoboard:main
    restart: unless-stopped
    ports:
      - "5005:5005"
```
