# KipoBoard

Simple Pinterest image search proxy.

## Demo

https://kipoboard.daniisaahir.com

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py --server.port=5005 --server.address=0.0.0.0 --server.headless=true
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
