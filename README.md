# dinterest

Simple Pinterest image search proxy written in Go.

## Instance

https://dinterest.daniisaahir.com

## Screenshot

<img width="1888" height="912" alt="image" src="https://github.com/user-attachments/assets/76e4999c-8ceb-4ede-96f3-b221ab290b46" />


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
