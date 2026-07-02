# kipoboard
Pinterest image search proxy written in Go.
## Instance
https://kipoboard.daniisaahir.com
## Local Setup
```bash
go run main.go
```
## Docker Run
```yaml
docker run --name kipoboard --restart unless-stopped -u 1000:1000 --security-opt no-new-privileges:true --cap-drop ALL --dns 1.1.1.1 --dns 1.0.0.1 --read-only -p 5005:5005 ghcr.io/dsbok/kipoboard:latest
```
