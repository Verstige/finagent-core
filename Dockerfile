FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nova_webhook.py .
COPY nova_core/ nova_core/

ENV PORT=8080

CMD ["python", "nova_webhook.py"]