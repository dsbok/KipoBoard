# dinterest

Simple Pinterest image search proxy written in Go.

## Run

```bash
go run main.go
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