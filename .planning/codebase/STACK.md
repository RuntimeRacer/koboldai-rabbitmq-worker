# 技术栈

**分析日期:** 2026-03-30

## 语言

**主要:**
- Python 3.9 - 主程序开发语言

**次要:**
- Shell脚本 (run.sh) - 启动脚本

## 运行时

**环境:**
- Python 3.9+

**包管理:**
- pip
- 依赖文件：requirements.txt
- 锁文件：无

## 框架

**核心:**
- pika - RabbitMQ客户端库，用于连接和操作RabbitMQ
- requests - HTTP客户端库，用于向推理服务器发送请求

**测试:**
- 无正式测试框架

**构建/开发:**
- Docker - 容器化部署
- docker-compose - 本地开发和测试

## 关键依赖

**关键:**
- pika - RabbitMQ消息队列客户端
- requests - HTTP请求库，用于与KoboldAI推理服务器通信

**基础设施:**
- Python标准库：json, os, argparse, sys, time, logging, functools

## 配置

**环境:**
- 通过命令行参数传入配置（argparse）
- Docker环境变量配置（Dockerfile）
- 必需参数：
  - RABBITMQ_USER：RabbitMQ用户名
  - RABBITMQ_PASS：RabbitMQ密码
  - RABBITMQ_HOST：RabbitMQ主机地址
  - RABBITMQ_PORT：RabbitMQ端口（默认5672）
  - POLL_QUEUE：消费队列名称
  - PUSH_QUEUE：推送结果队列名称
  - INFERENCE_SERVER_HOST：推理服务器地址
  - MODEL_NAME：模型名称（可选）

**构建:**
- `Dockerfile`：Python 3.9-slim基础镜像
- `docker-compose.yml`：RabbitMQ服务定义

## 平台要求

**开发:**
- Python 3.9+
- RabbitMQ服务器

**生产:**
- Docker容器环境
- RabbitMQ服务可用
- 推理服务器可访问

---

*技术栈分析: 2026-03-30*