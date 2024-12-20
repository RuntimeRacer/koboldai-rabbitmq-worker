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
import functools

from logging import Formatter


def ack_message(ch, delivery_tag):
    if ch.is_open:
        ch.basic_ack(delivery_tag)
    else:
        # Channel is already closed, so we can't ACK this message;
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
            cache_size: int = 1,
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
        if cache_size < 0:
            raise RuntimeError("invalid cache size")
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
        self.cache_thread = None
        self.cache_size = cache_size
        self.cached_messages = []
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
                self.polling_channel_ref.basic_qos(prefetch_count=self.cache_size + 1)
                self.polling_channel_ref.queue_declare(queue=self.poll_channel, durable=True)
                self.connection_active = True
                logging.info("Successfully connected to RabbitMQ host")
            except RuntimeError as e:
                logging.error("Unable to connect to RabbitMQ host: {}".format(str(e)))
                logging.error("Retrying in 10 seconds...")
                time.sleep(10)
                continue

            # Add cache processing thread and start it
            self.cache_thread = CacheProcessingThread(worker=self)
            self.cache_thread.start()

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
            'MessageMetadata': message_metadata,
            'ChannelRef': channel,
            'DeliveryTag': method.delivery_tag
        })
        logging.debug("Added message with ID {} to cache".format(message_id))

        # Check for Cache capacity and block if reached
        if len(self.cached_messages) > self.cache_size:
            # Send log line only once here, to avoid logspam
            logging.debug("Cache is full, waiting for clearance...".format(message_id))
            # Wait until cache is cleared
            while len(self.cached_messages) > self.cache_size:
                time.sleep(0.1)

    def process_cached_messages(self):
        while len(self.cached_messages) > 0:
            # Get first message from cache
            message = self.cached_messages[0]
            message_body = message['MessageBody']
            # Get RabbitMQ related data
            channel = message['ChannelRef']
            delivery_tag = message['DeliveryTag']

            # Send Request to target inference server
            result_json = {}
            if self.api_mode == "openai":
                # Add model name if defined
                if len(self.model_name) > 0:
                    message_body['model'] = self.model_name

                headers = {
                    "Content-Type": "application/json",
                }
                url = self.inference_server_host + "/v1/completions"

                try:
                    result = requests.post(url=url, headers=headers, json=message_body)
                except Exception as e:
                    logging.error("Inference server was unable to process message: {}".format(str(e)))
                    logging.error("Retrying in 10 seconds...")
                    time.sleep(10)
                    continue

                # Build Result
                try:
                    result = {
                        "MessageID": message['MessageID'],
                        "MessageBody": message['MessageBody'],
                        "MessageMetadata": message['MessageMetadata'],
                        "ResultStatus": result.status_code,
                        "ResultBody": result.json(),
                    }
                    result_json = json.dumps(result)
                except Exception as e:
                    logging.error("failed to decode result from inference server: {}".format(str(e)))
                    logging.error("Retrying in 10 seconds...")
                    time.sleep(10)
                    continue

            elif self.api_mode == "legacy":
                headers = {
                    "Content-Type": "application/json",
                }
                url = self.inference_server_host + "/api/v1/generate"
                try:
                    result = requests.post(url=url, headers=headers, json=message_body)
                except Exception as e:
                    logging.error("Inference server was unable to process message: {}".format(str(e)))
                    logging.error("Retrying in 10 seconds...")
                    time.sleep(10)
                    continue

                # Build Result
                try:
                    result = {
                        "MessageID": message['MessageID'],
                        "MessageMetadata": message['MessageMetadata'],
                        "ResultStatus": result.status_code,
                        "ResultBody": result.text,
                    }
                    result_json = json.dumps(result)
                except Exception as e:
                    logging.error("failed to decode result from inference server: {}".format(str(e)))
                    logging.error("Retrying in 10 seconds...")
                    time.sleep(10)
                    continue

            # Remove message from cache, AFTER being processed
            self.cached_messages.pop(0)
            # Send ACK to tasks channel
            cb = functools.partial(ack_message, channel, delivery_tag)
            self.polling_connection.add_callback_threadsafe(cb)
                
            # Publish to result queue
            logging.info("Processing for message ID '{0}' completed. Sending Result: {1}".format(message['MessageID'], result_json))
            result_sent = False
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
                result_sent = True
                self.pushing_channel_ref.close()
                self.pushing_connection.close()
            except Exception as e:
                if not result_sent:
                    logging.error("Failed to send result: {0}".format(str(e)))
                else:
                    logging.warning("Exception after sending result: {0}".format(str(e)))

                # Shutdown connections & processing after exception
                self.shutdown()

            if result_sent:
                logging.info("Result for message ID '{0}' was sent successfully!".format(message['MessageID']))

    def shutdown(self):
        if self.cache_thread is not None:
            self.cache_thread.active = False
            self.cached_messages.clear()
            self.cache_thread.join()

        if self.pushing_channel_ref is not None:
            try:
                self.pushing_channel_ref.close()
            except Exception as e:
                logging.warning("failed to shutdown pushing channel gracefully: {0}".format(str(e)))

        if self.pushing_connection is not None:
            try:
                self.pushing_connection.close()
            except Exception as e:
                logging.warning("failed to shutdown pushing connection gracefully: {0}".format(str(e)))

        if self.polling_channel_ref is not None:
            try:
                self.polling_channel_ref.stop_consuming()
                self.polling_channel_ref.close()
            except Exception as e:
                logging.warning("failed to shutdown polling channel gracefully: {0}".format(str(e)))

        if self.polling_connection is not None:
            try:
                self.polling_connection.close()
            except Exception as e:
                logging.warning("failed to shutdown polling connection gracefully: {0}".format(str(e)))

        self.connection_active = False


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
    parser.add_argument("-ih", "--inference_server_host", type=str, help="host+port of the inference server")

    # Worker Parameters
    parser.add_argument("-cs", "--cache_size", type=int, default=1, help="amount of messages to cache while processing")

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
