# kipoboard
Pinterest image search proxy written in Go.
## Instance
https://kipoboard.daniisaahir.com
## Local Setup
```bash
go run main.go
```
## Compose
```yaml
services:
  kipoboard:
    image: ghcr.io/dsbok/kipoboard:latest
    container_name: kipoboard
    restart: unless-stopped
    ports:
      - "5005:5005"
```
