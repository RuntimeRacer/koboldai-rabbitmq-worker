#!/bin/bash

RABBITMQ_USER=$1
RABBITMQ_PASS=$2
RABBITMQ_HOST=$3
RABBITMQ_PORT=$4
POLL_QUEUE=$5
PUSH_QUEUE=$6
INFERENCE_SERVER_HOST=$7
CACHE_SIZE=$8
MODEL_NAME=$9

until python3 rabbitmq.py -u "$RABBITMQ_USER" -p "$RABBITMQ_PASS" -rh "$RABBITMQ_HOST" -rp "$RABBITMQ_PORT" -pl "$POLL_QUEUE" -pu "$PUSH_QUEUE" -ih "$INFERENCE_SERVER_HOST" -cs "$CACHE_SIZE" -m "$MODEL_NAME"; do
    timestamp=$(date -u +"[%Y-%m-%d %H:%M:%S %z]")
    echo "${timestamp} RabbitMQ worker crashed with exit code $?.  Respawning.." >&2
    sleep 1
done