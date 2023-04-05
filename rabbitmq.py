# RabbitMQ request processor for KoboldAI - (c) 2023 RuntimeRacer
# Simple, synchronous processor for KoboldAI requests when using RabbitMQ to make it useable as a service
# (Main Reason I do it is because 11k aiserver.py is ridiculous)
import json
import os
import argparse
import sys

import pika
import requests


class RabbitMQWorker:
    def __init__(self, rabbitmq_user: str, rabbitmq_pass: str, rabbitmq_host: str, rabbitmq_port: int, poll_channel: str, push_channel: str, koboldai_host: str):
        # Very simple validity checks
        if len(rabbitmq_user) == 0:
            raise RuntimeError("rabbitmq_user not set")
        if len(rabbitmq_pass) == 0:
            raise RuntimeError("rabbitmq_pass not set")
        if len(rabbitmq_host) == 0:
            raise RuntimeError("rabbitmq_host not set")
        if len(poll_channel) == 0:
            raise RuntimeError("poll_channel not set")
        if len(push_channel) == 0:
            raise RuntimeError("push_channel not set")
        if len(koboldai_host) == 0:
            raise RuntimeError("koboldai_host not set")

        # Setup Params
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.poll_channel = poll_channel
        self.push_channel = push_channel
        self.koboldai_host = koboldai_host

        # Handling params
        self.polling_connection = None
        self.polling_channel_ref = None
        self.pushing_connection = None
        self.pushing_channel_ref = None

    def run(self):
        # Connect to RabbitMQ
        try:
            self.polling_connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=pika.credentials.PlainCredentials(username=self.rabbitmq_user, password=self.rabbitmq_pass)
            ))
            self.polling_channel_ref = self.polling_connection.channel()
            self.polling_channel_ref.queue_declare(queue=self.poll_channel)
        except RuntimeError as e:
            print("Unable to connect to RabbitMQ host: {}".format(str(e)))
            raise e

        # Start listening
        self.polling_channel_ref.basic_consume(queue=self.poll_channel, on_message_callback=self.handle_prompt_message, auto_ack=True)
        print("Listening for messages on queue {}...".format(self.poll_channel))
        sys.stdout.flush()
        self.polling_channel_ref.start_consuming()

    """
    Expecting the following structure in param 'body':    
    {
        "MessageID": str, // ID of the message defined by the sender, can be general UUID
        "MessageBody": str // Request Body 
        "MessageMetadata": str // Metadata for context to be shared between request sender and result receiver
    }
    
    Returns the following structure in result:
    {
        "MessageID": str, // ID of the message defined by the sender, can be general UUID
        "MessageMetadata": str // Metadata for context to be shared between request sender and result receiver
        "ResultStatus": str, // Status code of the response
        "ResultBody": str // Body of the response
    }
    """
    def handle_prompt_message(self, channel, method, properties, body):
        # Parse message
        print("Received message from channel '{}': {}".format(self.poll_channel, body))
        data = json.loads(body)
        message_id = data['MessageID']
        message_body = data['MessageBody']
        message_metadata = data['MessageMetadata'] if 'MessageMetadata' in data else ''

        # Send Request to target KoboldAI server
        headers = {
            "Content-Type": "application/json",
        }
        url = self.koboldai_host + "/api/v1/generate"
        result = requests.post(url=url, headers=headers, json=message_body)

        # Build Result
        result = {
            "MessageID": message_id,
            "MessageMetadata": message_metadata,
            "ResultStatus": result.status_code,
            "ResultBody": result.text,
        }
        result_json = json.dumps(result)

        # Publish to result queue
        print("Sending result for message ID '{}': {}".format(message_id, result_json))
        self.pushing_connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            credentials=pika.credentials.PlainCredentials(username=self.rabbitmq_user, password=self.rabbitmq_pass)
        ))
        self.pushing_channel_ref = self.pushing_connection.channel()
        self.pushing_channel_ref.queue_declare(queue=self.push_channel)
        self.pushing_channel_ref.basic_publish(exchange='', routing_key=self.push_channel, body=result_json)
        self.pushing_channel_ref.close()
        self.pushing_connection.close()
        # Flush stdout on every message handling
        sys.stdout.flush()

    def shutdown(self):
        if self.polling_channel_ref is not None:
            self.polling_channel_ref.stop_consuming()
        if self.polling_connection is not None:
            self.polling_connection.close()

if __name__ == "__main__":
    global _polling_connection, _polling_channel, _pushing_connection

    # Parse from arguments
    parser = argparse.ArgumentParser()

    # MQ Parameters
    parser.add_argument("-u", "--rabbitmq_user", type=str, help="username to establish broker connection")
    parser.add_argument("-p", "--rabbitmq_pass", type=str, help="password to establish broker connection")
    parser.add_argument("-rh", "--rabbitmq_host", type=str, help="host of the rabbitmq server")
    parser.add_argument("-rp", "--rabbitmq_port", type=int, default=5672, help="port of the rabbitmq server")
    parser.add_argument("-pl", "--poll_channel", type=str, help="name if the rabbitmq channel to subscribe to")
    parser.add_argument("-pu", "--push_channel", type=str, help="name if the rabbitmq channel to push results to")

    # KoboldAI Parameters
    parser.add_argument("-kh", "--koboldai_host", type=str, help="host+port of the koboldai server")

    # Run
    args = parser.parse_args()
    worker = RabbitMQWorker(**vars(args))
    try:
        worker.run()
    except KeyboardInterrupt:
        print("Manual Interrupt!")
        # Try clean shutdown
        worker.shutdown()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
