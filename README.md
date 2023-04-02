# RabbitMQ Worker for KoboldAI
This is a small worker utility which I wrote to overcome technical limitations observed when
hosting KoboldAI as an OnPremise service for an AI Chat App unsing Pygmalion-6B.

#### Background:
The Way KoboldAI is structured, it's not able to process more than one 'generate'-request at a time.
There might be better / smarter ways to fix this, however I didn't want to spend a week or two to
understand KoboldAI's ridiculous 11k lines aiserver.py + refactor it on my own.

## Description
This repo contains 3 files:
- rabbitmq.py: main script of my worker, containing a small class
- rabbitmq_test.py: small script to feed a queue, content should then be picked up and processed by the worker
- docker-compose.yml: Optional; docker-compose file to run RabbitMQ as a docker service.

The worker script connects to a RabbitMQ Message Broker and starts listening to a specified input queue.
Once messages are pushed to that queue, it will try to parse them and forward them to a specified
KoboldAI host by calling the `/v1/generate` endpoint and providing the body specified in the input
message. Once KoboldAI returns, the result will be parsed and pushed into another queue, the result queue.
Once the result has been pushed, the worker will listen to the input queue again and repeats the described
procedure for each incoming message.

To run it, simply execute:
```
python rabbitmq.py -u {USER} -p {PASSWORD} -rh rabbitmq.host -rp 5672 -pl "pygmalion_requests" -pu "pygmalion_results" -kh http://koboldai.host:5000
```
For details on the individual parameters, please check the argparse section at the bottom.
All Parameters are mandatory.

## Further References & useful links
- KoboldAI Client by henk717: https://github.com/henk717/KoboldAI/
- Simple Setup Guide for Pygmalion / KoboldAI on your own Machine: https://rentry.org/pygmalion-local#running-pygmalion-on-the-cloud
- RabbitMQ Python Tutorial: https://www.rabbitmq.com/tutorials/tutorial-one-python.html
- Setting up nginx TCP upstream for RabbitMQ: https://medium.com/@giorgos.dyrrahitis/configuring-an-nginx-tcp-proxy-for-my-rabbitmq-cluster-under-10-minutes-a0731ec6bfaf
- Setting up AMQP over TLS: https://medium.com/dlt-labs-publication/how-to-set-up-an-ssl-tls-enabled-rabbitmq-server-3e4e47315e8b

## License
Like KoboldAI, this repo is also licensed with a AGPL license.
In short this means that it can be used by anyone
for any purpose. However, if you decide to make a publicly available instance your users are
entitled to a copy of the source code including all modifications that you have made (which needs
to be available trough an interface such as a button on your website), you may also not distribute
this project in a form that does not contain the source code (Such as compiling / encrypting the
code and distributing this version without also distributing the source code that includes the
changes that you made. You are allowed to distribute this in a closed form if you also provide a
separate archive with the source code.).