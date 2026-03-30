# 外部集成

**分析日期:** 2026-03-30

## API与外部服务

**消息队列:**
- RabbitMQ - 消息代理
  - 客户端：pika (Python库)
  - 认证：PlainCredentials (用户名/密码)
  - 端口：5672 (AMQP), 5671 (AMQPS/TLS), 15672 (管理UI)
  - 消费队列：poll_channel参数指定
  - 推送队列：push_channel参数指定

**推理服务:**
- KoboldAI兼容API - LLM推理后端
  - 支持两种模式：
    - OpenAI格式：POST到 `/v1/completions`
    - Legacy格式：POST到 `/api/v1/generate`
  - 客户端：requests库
  - 超时：30秒
  - 认证：自定义（取决于推理服务器配置）

## 数据存储

**消息存储:**
- RabbitMQ - 消息持久化队列
- 队列声明：`queue_declare(queue=name, durable=True)`
- 持久化：durable=True确保消息持久化

**文件存储:**
- 本地文件系统：无持久化需求

**缓存:**
- 无缓存层

## 认证与身份

**RabbitMQ认证:**
- 方式：PlainCredentials (简单用户名/密码)
- 实现：`pika.credentials.PlainCredentials(username, password)`
- 参数：rabbitmq_user, rabbitmq_pass

**推理服务器认证:**
- 方式：无内置认证（依赖服务器配置）
- 可扩展：可通过添加自定义Header实现

## 监控与可观测性

**日志:**
- 框架：Python logging模块
- 级别：DEBUG (主程序), WARNING (pika库)
- 格式：`[时间戳] 级别: 消息`
- 输出：stdout

**健康检查:**
- 无内置健康检查端点

## CI/CD与部署

**托管:**
- Docker容器化部署
- 支持docker-compose本地开发

**CI/CD:**
- 无CI/CD流水线

## 环境配置

**必需环境变量:**
- RABBITMQ_USER：RabbitMQ用户名
- RABBITMQ_PASS：RabbitMQ密码
- RABBITMQ_HOST：RabbitMQ主机地址
- RABBITMQ_PORT：RabbitMQ端口（默认5672）
- POLL_QUEUE：消费队列名称
- PUSH_QUEUE：推送队列名称
- INFERENCE_SERVER_HOST：推理服务器地址
- MODEL_NAME：模型名称（可选）

**参数位置:**
- Dockerfile：ENV指令定义
- docker-compose.yml：environment节
- 运行时：命令行参数

## Webhook与回调

**接收:**
- RabbitMQ消费者：监听队列消息

**发送:**
- RabbitMQ生产者：推送结果到结果队列

---

*集成审计: 2026-03-30*