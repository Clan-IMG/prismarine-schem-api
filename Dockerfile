FROM python:3.11-slim

RUN apt update && apt install -y curl iputils-ping gcc libffi-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

RUN python .api/build.py || true

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2} --timeout-keep-alive 75 --backlog 4096"]
