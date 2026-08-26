FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/backend/requirements.txt

COPY backend /app/backend
COPY data/scripts /app/data/scripts
COPY data/processed /app/data/processed

RUN mkdir -p /app/data/raw/reddit
RUN mkdir -p /app/data/processed/qualitative

WORKDIR /app/backend

EXPOSE 8000

CMD [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]