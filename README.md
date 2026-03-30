# RabbitMQ Worker for KoboldAI

A message queue worker that enables parallel request processing for KoboldAI instances. This worker bridges RabbitMQ message queues with KoboldAI's inference API, allowing multiple generation requests to be queued and processed efficiently.

## Background

KoboldAI is structured to process only one generation request at a time. This worker solves that limitation by acting as an intermediary - receiving requests from a RabbitMQ queue, forwarding them to KoboldAI, and returning results to another queue for downstream processing.

## Features

- **Message Queue Integration**: Connects to RabbitMQ to consume requests and publish results
- **Dual API Mode Support**: Compatible with both OpenAI format (`/v1/completions`) and KoboldAI legacy format (`/api/v1/generate`)
- **Docker Support**: Containerized deployment with Docker and docker-compose
- **Graceful Shutdown**: Proper connection management on shutdown

## Technology Stack

- **Language**: Python 3.9+
- **Message Broker**: RabbitMQ (via pika)
- **HTTP Client**: requests
- **Deployment**: Docker, docker-compose

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up RabbitMQ (optional - using docker-compose):
```bash
docker-compose up -d
```

## Configuration

All parameters are passed via command-line arguments:

| Parameter | Description |
|-----------|-------------|
| `-u`, `--user` | RabbitMQ username |
| `-p`, `--password` | RabbitMQ password |
| `-rh`, `--rabbitmq-host` | RabbitMQ host address |
| `-rp`, `--rabbitmq-port` | RabbitMQ port (default: 5672) |
| `-pl`, `--poll-queue` | Input queue name to consume from |
| `-pu`, `--push-queue` | Output queue name to publish results |
| `-kh`, `--koboldai-host` | KoboldAI server URL |
| `-am`, `--api-mode` | API mode: `openai` or `legacy` (default: legacy) |

## Usage

Start the worker:
```bash
python rabbitmq.py \
  -u RABBITMQ_USER \
  -p RABBITMQ_PASSWORD \
  -rh rabbitmq.host \
  -rp 5672 \
  -pl "pygmalion_requests" \
  -pu "pygmalion_results" \
  -kh http://koboldai.host:5000
```

Send a test message:
```bash
python rabbitmq_test.py
```

## Message Format

**Request:**
```json
{
  "MessageID": "unique-id",
  "MessageBody": {
    "prompt": "Your prompt here...",
    "temperature": 0.7,
    "max_tokens": 500
  },
  "MessageMetadata": {}
}
```

**Response:**
```json
{
  "MessageID": "unique-id",
  "MessageMetadata": {},
  "ResultStatus": "success",
  "ResultBody": {
    "text": "Generated text..."
  }
}
```

## Docker Deployment

```bash
# Build the image
docker build -t koboldai-rabbitmq-worker .

# Run the container
docker run -d \
  -e RABBITMQ_USER=username \
  -e RABBITMQ_PASSWORD=password \
  -e RABBITMQ_HOST=rabbitmq \
  -e POLL_QUEUE=requests \
  -e PUSH_QUEUE=results \
  -e INFERENCE_SERVER_HOST=http://koboldai:5000 \
  koboldai-rabbitmq-worker
```

## Project Structure

```
koboldai-rabbitmq-worker/
├── rabbitmq.py           # Main worker implementation
├── rabbitmq_test.py      # Test script for sending messages
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # RabbitMQ service for local development
└── run.sh                # Startup script with auto-restart
```

## Documentation Links

- [KoboldAI Client](https://github.com/henk717/KoboldAI/)
- [Pygmalion Local Setup Guide](https://rentry.org/pygmalion-local)
- [RabbitMQ Python Tutorial](https://www.rabbitmq.com/tutorials/tutorial-one-python.html)

## License

AGPL - See [LICENSE](LICENSE) file for details.