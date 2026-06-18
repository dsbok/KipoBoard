FROM python:3.12-alpine
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5005", "app:app"]
