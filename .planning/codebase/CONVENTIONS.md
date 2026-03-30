# 编码规范

**分析日期:** 2026-03-30

## 命名模式

**文件:**
- snake_case：使用小写字母和下划线，如 `rabbitmq.py`, `rabbitmq_test.py`

**函数:**
- snake_case：小写字母加下划线，如 `ack_message`, `handle_prompt_message`

**变量:**
- snake_case：小写字母加下划线，如 `rabbitmq_user`, `polling_connection`

**类型:**
- PascalCase：类名使用大写字母开头，如 `RabbitMQWorker`

## 代码风格

**格式化:**
- 无自动格式化工具配置
- 遵循PEP 8基本规范

**linting:**
- 无linting配置

**缩进:**
- 4空格缩进

## 导入组织

**顺序:**
1. Python标准库：json, os, argparse, sys, time, logging, functools
2. 第三方库：pika, requests
3. 本地导入：无

**示例 (rabbitmq.py):**
```python
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
```

## 错误处理

**模式:**
- try-except块捕获异常
- 使用functools.partial进行线程安全的回调处理
- graceful shutdown模式清理资源

**示例 (rabbitmq.py 第181-186行):**
```python
except Exception as e:
    logging.error("An error occurred during message processing: {}".format(str(e)))
    # Send negative acknowledgment to requeue the message
    cb = functools.partial(nack_message, channel, method.delivery_tag)
    self.polling_connection.add_callback_threadsafe(cb)
    return
```

## 日志

**框架:** Python logging模块

**模式:**
- UTC时间戳：`Formatter.converter = time.gmtime`
- 格式：`[%(asctime)s] %(levelname)s: %(message)s`
- 日期格式：`%Y-%m-%d %H:%M %S %z`
- pika库日志级别设为WARNING避免日志刷屏

**示例 (rabbitmq.py 第247-255行):**
```python
Formatter.converter = time.gmtime
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S %z'
)
# Pika log level to warning to avoid logspam
logging.getLogger("pika").setLevel(logging.WARNING)
```

## 注释

**何时注释:**
- 文件头部版权和用途说明
- 方法文档字符串说明参数和返回值格式

**示例 (rabbitmq.py 第112-127行):**
```python
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
```

## 函数设计

**大小:** 单个方法职责明确，不超过100行

**参数:**
- 使用类型注解（Type Hints）
- 必需参数使用位置参数
- 可选参数使用默认值

**返回值:**
- 明确返回值或无返回值（通过回调处理）

## 模块设计

**导出:** 无模块导出概念（单文件脚本）

**Barrel文件:** 无

---

*规范分析: 2026-03-30*