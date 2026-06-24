# kipoboard
Pinterest image search proxy.
## Instance
https://kipoboard.daniisaahir.com
## Local Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 app.py
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
