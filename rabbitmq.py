# RabbitMQ request processor for KoboldAI - (c) 2023 RuntimeRacer
# Simple, synchronous processor for KoboldAI requests when using RabbitMQ to make it useable as a service
# (Main Reason I do it is because 11k aiserver.py is ridiculous)
import json
import os
import argparse
import sys
import threading
import time

import pika
import requests
import logging

from logging import Formatter


class RabbitMQWorker:
    def __init__(
            self,
            rabbitmq_user: str,
            rabbitmq_pass: str,
            rabbitmq_host: str,
            rabbitmq_port: int,
            poll_channel: str,
            push_channel: str,
            kobold_ai_host: str,
            cache_size: int = 1
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
        if len(kobold_ai_host) == 0:
            raise RuntimeError("koboldai_host not set")
        if cache_size < 0:
            raise RuntimeError("invalid cache size")

        # Setup Params
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.poll_channel = poll_channel
        self.push_channel = push_channel
        self.kobold_ai_host = kobold_ai_host

        # Handling params
        self.cache_thread = None
        self.cache_size = cache_size
        self.cached_messages = []
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
                credentials=pika.credentials.PlainCredentials(username=self.rabbitmq_user, password=self.rabbitmq_pass),
                heartbeat=30
            ))
            self.polling_channel_ref = self.polling_connection.channel()
            self.polling_channel_ref.queue_declare(queue=self.poll_channel, durable=True)
        except RuntimeError as e:
            logging.error("Unable to connect to RabbitMQ host: {}".format(str(e)))
            raise e

        # Add cache processing thread and start it
        self.cache_thread = CacheProcessingThread(worker=self)
        self.cache_thread.start()

        # Start listening
        try:
            self.polling_channel_ref.basic_consume(queue=self.poll_channel, on_message_callback=self.handle_prompt_message, auto_ack=True)
            logging.info("Listening for messages on queue {}...".format(self.poll_channel))
            self.polling_channel_ref.start_consuming()
        except Exception as e:
            logging.error("Lost connection to RabbitMQ host: {}".format(str(e)))
            # Shutdown cache processing thread
            self.cache_thread.active = False
            self.cache_thread.join()
            raise e

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
        message_id = data['MessageID'] if 'MessageID' in data else ''
        message_body = data['MessageBody'] if 'MessageBody' in data else ''
        message_metadata = data['MessageMetadata'] if 'MessageMetadata' in data else ''

        # Only process valid data
        if len(message_id) == 0 or len(message_body) == 0:
            logging.warning("Message received was invalid. Skipping...")
            return

        # Add to cache - Before checking cache size
        # This ensures we always process at least one message, even if cache is set to 0, because
        # due to async nature oft the worker, it will always pull at least 1 message no matter what.
        # Cache check will check cache size after adding the message, so this pulling connection is blocked until
        # Cache is freed up again.
        self.cached_messages.append({
            'MessageID': message_id,
            'MessageBody': message_body,
            'MessageMetadata': message_metadata
        })
        logging.debug("Added message with ID {} to cache".format(message_id))

        # Check for Cache capacity and block if reached
        while len(self.cached_messages) > self.cache_size:
            logging.debug("Cache is full, waiting for clearance...".format(message_id))
            time.sleep(0.1)

    def process_cached_messages(self):
        while len(self.cached_messages) > 0:
            # Get first message from cache
            message = self.cached_messages[0]

            # Quickfix: Handle change of token param name
            message_body = message['MessageBody']
            if "max_new_tokens" in message_body:
                message_body["max_tokens"] = message_body["max_new_tokens"]
                del message_body["max_new_tokens"]

            # Send Request to target KoboldAI server
            headers = {
                "Content-Type": "application/json",
            }
            url = self.kobold_ai_host + "/v1/completions"
            result = requests.post(url=url, headers=headers, json=message_body)
            # Remove message from cache, AFTER being processed
            self.cached_messages.pop(0)

            # Build Result
            result = {
                "MessageID": message['MessageID'],
                "MessageMetadata": message['MessageMetadata'],
                "ResultStatus": result.status_code,
                "ResultBody": result.json(),
            }
            result_json = json.dumps(result)

            # Publish to result queue
            logging.info("Sending result for message ID '{}': {}".format(message['MessageID'], result_json))
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

    def shutdown(self):
        if self.polling_channel_ref is not None:
            self.polling_channel_ref.stop_consuming()
        if self.polling_connection is not None:
            self.polling_connection.close()
        if self.cache_thread is not None:
            self.cache_thread.active = False
            self.cache_thread.join()


class CacheProcessingThread(threading.Thread):

    def __init__(self, worker: RabbitMQWorker):
        # execute the base constructor
        threading.Thread.__init__(self)
        # store the reference
        self.worker = worker
        # Internal vars
        self.active = False

    def run(self):
        if self.worker is not None:
            logging.info("Starting Cache Processing Thread")
            self.active = True
            while self.active:
                self.worker.process_cached_messages()
                # Sleep if not processing anything
                time.sleep(0.01)
        else:
            raise RuntimeError("RabbitMQ Worker not initialized")


if __name__ == "__main__":
    global _polling_connection, _polling_channel, _pushing_connection

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
    parser.add_argument("-pl", "--poll_channel", type=str, help="name if the rabbitmq channel to subscribe to")
    parser.add_argument("-pu", "--push_channel", type=str, help="name if the rabbitmq channel to push results to")

    # KoboldAI Parameters
    parser.add_argument("-kh", "--kobold_ai_host", type=str, help="host+port of the koboldai server")

    # Worker Parameters
    parser.add_argument("-cs", "--cache_size", type=int, default=1, help="amount of messages to cache while processing")

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
