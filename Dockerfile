FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./src /app
COPY requirements.txt /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port \$PORT"]