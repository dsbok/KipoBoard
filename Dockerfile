FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5005
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5005", "app:app"]
