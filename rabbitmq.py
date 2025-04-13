# RabbitMQ request processor for KoboldAI - (c) 2023 RuntimeRacer
# Simple, synchronous processor for KoboldAI requests when using RabbitMQ to make it useable as a service
# (Main Reason I do it is because 11k aiserver.py is ridiculous)
import json
import os
import argparse
import sys
import time

import pika
import requests
import logging
import functools

from logging import Formatter


def ack_message(ch, delivery_tag):
    if ch.is_open:
        ch.basic_ack(delivery_tag)
    else:
        # Channel is already closed, so we can't ACK this message
        pass


def nack_message(ch, delivery_tag):
    if ch.is_open:
        ch.basic_nack(delivery_tag, requeue=True)
    else:
        # Channel is already closed, so we can't NACK this message
        pass


class RabbitMQWorker:
    def __init__(
        self,
        rabbitmq_user: str,
        rabbitmq_pass: str,
        rabbitmq_host: str,
        rabbitmq_port: int,
        poll_channel: str,
        push_channel: str,
        inference_server_host: str,
        api_mode: str = "openai",  # either 'openai' for new format, or 'legacy' for old KoboldAI format
        model_name: str = ''
    ):
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
        if len(inference_server_host) == 0:
            raise RuntimeError("inference_server_host not set")
        if api_mode not in ["openai", "legacy"]:
            raise RuntimeError(f"invalid api mode '{api_mode}'")

        # Setup Params
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.poll_channel = poll_channel
        self.push_channel = push_channel
        self.inference_server_host = inference_server_host

        # Handling params
        self.connection_active = False
        self.polling_connection = None
        self.polling_channel_ref = None
        self.pushing_connection = None
        self.pushing_channel_ref = None
        self.api_mode = api_mode
        self.model_name = model_name

    def run(self):
        # Connect to RabbitMQ
        while not self.connection_active:
            try:
                self.polling_connection = pika.BlockingConnection(pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    port=self.rabbitmq_port,
                    credentials=pika.credentials.PlainCredentials(username=self.rabbitmq_user, password=self.rabbitmq_pass),
                    heartbeat=30
                ))
                self.polling_channel_ref = self.polling_connection.channel()
                self.polling_channel_ref.basic_qos(prefetch_count=1)
                self.polling_channel_ref.queue_declare(queue=self.poll_channel, durable=True)
                self.connection_active = True
                logging.info("Successfully connected to RabbitMQ host")
            except Exception as e:
                logging.error("Unable to connect to RabbitMQ host: {}".format(str(e)))
                logging.error("Retrying in 10 seconds...")
                time.sleep(10)
                continue

            # Start listening
            try:
                self.polling_channel_ref.basic_consume(queue=self.poll_channel, on_message_callback=self.handle_prompt_message)
                logging.info("Listening for messages on queue {}...".format(self.poll_channel))
                self.polling_channel_ref.start_consuming()
            except Exception as e:
                logging.error("Lost connection to RabbitMQ host: {}".format(str(e)))
                # Shutdown connections & processing after exception
                self.shutdown()

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
        logging.info("Received message from channel '{}': {}".format(self.poll_channel, body))
        data = json.loads(body)
        message_id = data.get('MessageID', '')
        message_body = data.get('MessageBody', '')
        message_metadata = data.get('MessageMetadata', '')

        # Only process valid data
        if not message_id or not message_body:
            logging.warning("Message received was invalid. Skipping...")
            # Acknowledge the invalid message to remove it from the queue
            cb = functools.partial(ack_message, channel, method.delivery_tag)
            self.polling_connection.add_callback_threadsafe(cb)
            return

        # Send Request to target inference server
        result_json = {}
        try:
            if self.api_mode == "openai":
                # Add model name if defined
                if self.model_name:
                    message_body['model'] = self.model_name

                headers = {
                    "Content-Type": "application/json",
                }
                url = self.inference_server_host + "/v1/completions"
                result = requests.post(url=url, headers=headers, json=message_body, timeout=30)
                # Build Result
                result_data = {
                    "MessageID": message_id,
                    "MessageBody": message_body,
                    "MessageMetadata": message_metadata,
                    "ResultStatus": result.status_code,
                    "ResultBody": result.json(),
                }
                result_json = json.dumps(result_data)
            elif self.api_mode == "legacy":
                headers = {
                    "Content-Type": "application/json",
                }
                url = self.inference_server_host + "/api/v1/generate"
                result = requests.post(url=url, headers=headers, json=message_body, timeout=30)
                # Build Result
                result_data = {
                    "MessageID": message_id,
                    "MessageMetadata": message_metadata,
                    "ResultStatus": result.status_code,
                    "ResultBody": result.text,
                }
                result_json = json.dumps(result_data)
        except Exception as e:
            logging.error("An error occurred during message processing: {}".format(str(e)))
            # Send negative acknowledgment to requeue the message
            cb = functools.partial(nack_message, channel, method.delivery_tag)
            self.polling_connection.add_callback_threadsafe(cb)
            return

        # Publish to result queue
        logging.info("Processing for message ID '{0}' completed. Sending Result: {1}".format(message_id, result_json))
        try:
            self.pushing_connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=pika.credentials.PlainCredentials(username=self.rabbitmq_user, password=self.rabbitmq_pass),
                heartbeat=30
            ))
            self.pushing_channel_ref = self.pushing_connection.channel()
            self.pushing_channel_ref.queue_declare(queue=self.push_channel, durable=True)
            self.pushing_channel_ref.basic_publish(exchange='', routing_key=self.push_channel, body=result_json)
            self.pushing_channel_ref.close()
            self.pushing_connection.close()
            logging.info("Result for message ID '{0}' was sent successfully!".format(message_id))
        except Exception as e:
            logging.error("Failed to send result: {0}".format(str(e)))
            # Send a negative acknowledgment to requeue the message
            cb = functools.partial(nack_message, channel, method.delivery_tag)
            self.polling_connection.add_callback_threadsafe(cb)
            # Shutdown connections & processing after exception
            self.shutdown()
            return

        # Acknowledge the message after successful processing
        cb = functools.partial(ack_message, channel, method.delivery_tag)
        self.polling_connection.add_callback_threadsafe(cb)

    def shutdown(self):
        if self.pushing_channel_ref is not None:
            try:
                self.pushing_channel_ref.close()
            except Exception as e:
                logging.warning("Failed to shutdown pushing channel gracefully: {0}".format(str(e)))

        if self.pushing_connection is not None:
            try:
                self.pushing_connection.close()
            except Exception as e:
                logging.warning("Failed to shutdown pushing connection gracefully: {0}".format(str(e)))

        if self.polling_channel_ref is not None:
            try:
                self.polling_channel_ref.stop_consuming()
                self.polling_channel_ref.close()
            except Exception as e:
                logging.warning("Failed to shutdown polling channel gracefully: {0}".format(str(e)))

        if self.polling_connection is not None:
            try:
                self.polling_connection.close()
            except Exception as e:
                logging.warning("Failed to shutdown polling connection gracefully: {0}".format(str(e)))

        self.connection_active = False


if __name__ == "__main__":
    # Init logger
    Formatter.converter = time.gmtime
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %z'
    )
    # Pika log level to warning to avoid logspam
    logging.getLogger("pika").setLevel(logging.WARNING)

    # Parse from arguments
    parser = argparse.ArgumentParser()

    # MQ Parameters
    parser.add_argument("-u", "--rabbitmq_user", type=str, help="username to establish broker connection")
    parser.add_argument("-p", "--rabbitmq_pass", type=str, help="password to establish broker connection")
    parser.add_argument("-rh", "--rabbitmq_host", type=str, help="host of the rabbitmq server")
    parser.add_argument("-rp", "--rabbitmq_port", type=int, default=5672, help="port of the rabbitmq server")
    parser.add_argument("-pl", "--poll_channel", type=str, help="name of the rabbitmq channel to subscribe to")
    parser.add_argument("-pu", "--push_channel", type=str, help="name of the rabbitmq channel to push results to")

    # KoboldAI Parameters
    parser.add_argument("-ih", "--inference_server_host", type=str, help="host+port of the inference server")

    # Backend Parameters
    parser.add_argument("-m", "--model_name", type=str, default='', help="explicit name of the model, required by some backends")

    # Run
    args = parser.parse_args()
    worker = RabbitMQWorker(**vars(args))
    try:
        worker.run()
    except KeyboardInterrupt:
        logging.info("Manual Interrupt!")
        # Try clean shutdown
        worker.shutdown()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
