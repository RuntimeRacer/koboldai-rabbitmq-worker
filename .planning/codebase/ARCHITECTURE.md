# 架构

**分析日期:** 2026-03-30

## 模式概述

**总体模式:** 消息队列工作器模式（Message Queue Worker Pattern）

**关键特性:**
- 异步消息处理：通过RabbitMQ接收请求消息
- 请求转发：将请求转发至KoboldAI推理服务器
- 结果返回：处理完成后将结果推送到结果队列
- 同步处理：单线程同步处理消息
- 支持双模式：兼容OpenAI格式和KoboldAI传统格式

## 层次结构

**消息接入层:**
- 目的：连接RabbitMQ并接收请求消息
- 位置：`rabbitmq.py` (第81-110行)
- 包含：`RabbitMQWorker.run()` 方法
- 依赖：pika库
- 使用方：主程序入口

**消息处理层:**
- 目的：解析消息并转发至推理服务器
- 位置：`rabbitmq.py` (第129-215行)
- 包含：`handle_prompt_message()` 方法
- 依赖：requests库、推理服务器
- 使用方：消息接入层回调

**结果推送层:**
- 目的：将处理结果推送至结果队列
- 位置：`rabbitmq.py` (第188-210行)
- 包含：推送逻辑和连接管理
- 依赖：pika库
- 使用方：消息处理层

**配置与参数层:**
- 目的：解析命令行参数和配置
- 位置：`rabbitmq.py` (第245-283行)
- 包含：argparse配置
- 依赖：argparse模块
- 使用方：主程序入口

## 数据流

**请求处理流程:**

1. 连接到RabbitMQ的.poll_channel队列
2. 等待接收消息（阻塞式消费）
3. 解析消息JSON，获取MessageID、MessageBody、MessageMetadata
4. 根据api_mode选择转发目标：
   - openai模式：POST到 `/v1/completions`
   - legacy模式：POST到 `/api/v1/generate`
5. 接收推理服务器响应
6. 构建结果数据，包含MessageID、MessageMetadata、ResultStatus、ResultBody
7. 连接到.push_channel队列并推送结果
8. 确认消息（ACK）从队列中移除

**状态管理:**
- 连接状态：通过`connection_active`标志管理
- 连接对象：维护polling_connection和pushing_connection两个独立连接

## 关键抽象

**RabbitMQWorker类:**
- 目的：封装RabbitMQ工作器的所有功能
- 示例：`rabbitmq.py` (第34-242行)
- 模式：面向对象设计，单例模式

**消息格式抽象:**
- 目的：统一请求和响应的消息结构
- 请求格式：`{MessageID, MessageBody, MessageMetadata}`
- 响应格式：`{MessageID, MessageMetadata, ResultStatus, ResultBody}`

## 入口点

**主入口:**
- 位置：`rabbitmq.py` (第245-286行)
- 触发：命令行执行 `python rabbitmq.py [参数]`
- 职责：初始化日志、解析参数、创建worker、启动运行

**测试入口:**
- 位置：`rabbitmq_test.py`
- 触发：命令行执行 `python rabbitmq_test.py`
- 职责：向队列发送测试消息

## 错误处理

**策略:**
- 连接失败：重试机制，10秒间隔
- 消息处理失败：NACK消息重新入队
- 推送失败：关闭连接并重启
- 无效消息：ACK跳过，防止阻塞队列

**模式:**
- 使用functools.partial进行线程安全回调
- graceful shutdown模式关闭各连接
- 日志记录关键错误信息

## 跨领域关注点

**日志:** 使用Python logging模块，UTC时间戳格式，pika库日志级别设为WARNING

**验证:** 构造函数中进行基础参数验证，检查必填字段

**认证:** 使用RabbitMQ PlainCredentials进行认证

---

*架构分析: 2026-03-30*