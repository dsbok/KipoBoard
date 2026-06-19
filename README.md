# KipoBoard

Pinterest image search proxy.


> [!NOTE]
> **Project Status:** This project is not abandoned, but instead is final and stable. It will not receive further updates or feature additions unless Pinterest changes their API structure, which would require a fix.

## Demo

https://kipoboard.daniisaahir.com

## Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

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
