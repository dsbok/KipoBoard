# dinterest

Simple Pinterest image search proxy written in Python.

## Instance

https://dinterest.daniisaahir.com

## Run

```bash
pip install -r requirements.txt
python3 main.py
```

Runs on:
http://localhost:5003

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
