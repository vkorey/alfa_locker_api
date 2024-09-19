FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install --only-upgrade -y \
    libexpat1 \
    libgssapi-krb5-2 \
    libk5crypto3 \
    libkrb5support0 \
    libsqlite3-0 \
    perl-base \
    zlib1g && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./src /app
COPY requirements.txt /app

RUN pip install --no-cache-dir -r requirements.txt

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port $PORT"