FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY rabbitmq.py .

ENV RABBITMQ_USER=""
ENV RABBITMQ_PASS=""
ENV RABBITMQ_HOST=""
ENV RABBITMQ_PORT=5672
ENV POLL_QUEUE=""
ENV PUSH_QUEUE=""
ENV INFERENCE_SERVER_HOST=""
ENV MODEL_NAME=""

ENTRYPOINT python3 rabbitmq.py \
    -u "$RABBITMQ_USER" \
    -p "$RABBITMQ_PASS" \
    -rh "$RABBITMQ_HOST" \
    -rp "$RABBITMQ_PORT" \
    -pl "$POLL_QUEUE" \
    -pu "$PUSH_QUEUE" \
    -ih "$INFERENCE_SERVER_HOST" \
    -m "$MODEL_NAME"
