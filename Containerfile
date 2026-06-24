FROM fedora:44

RUN dnf -y update && \
    dnf -y install python3 python3-pip && \
    dnf clean all

WORKDIR /app

COPY . .

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "app.py"]
