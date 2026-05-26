FROM python:3.11-slim

WORKDIR /app

COPY main.py .

EXPOSE 5003

CMD ["python", "main.py"]
