# kipoboard
Pinterest image search proxy.
> [!NOTE]
> **Project Status:** Stable. No updates planned unless Pinterest API changes require fix.
> 
## Demo
https://kipoboard.daniisaahir.com
## Local Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

```
## Podman (CLI)
```bash
podman run -d \
  --name kipoboard \
  --restart unless-stopped \
  -p 5005:5005 \
  ghcr.io/dsbok/kipoboard:latest

```
## Podman Compose
```yaml
services:
  kipoboard:
    image: ghcr.io/dsbok/kipoboard:latest
    restart: unless-stopped
    ports:
      - "5005:5005"

```
