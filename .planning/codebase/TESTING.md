# 测试模式

**分析日期:** 2026-03-30

## 测试框架

**运行器:**
- 无正式测试框架（pytest/unittest）
- 手动测试脚本

**断言库:**
- 无

**运行命令:**
```bash
# 运行主程序
python rabbitmq.py [参数]

# 运行测试脚本
python rabbitmq_test.py
```

## 测试文件组织

**位置:**
- 测试脚本独立文件：`rabbitmq_test.py`
- 与主代码同目录

**命名:**
- snake_case：`rabbitmq_test.py`

**结构:**
```
rabbitmq.py          # 主程序
rabbitmq_test.py     # 测试脚本
```

## 测试结构

**手动测试:**
- 简单的消息发送测试
- 硬编码测试数据

**示例 (rabbitmq_test.py):**
```python
import json
import os
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(
    host='localhost',
    port=6000,
    credentials=pika.credentials.PlainCredentials(
        username=os.environ.get("RABBITMQ_USER"),
        password=os.environ.get("RABBITMQ_PASS")
    )))
channel = connection.channel()

channel.queue_declare(queue='pygmalion_requests')

message_data = {
    "MessageID": "test-ID",
    "MessageBody": {
        "prompt": "Niko the kobold stalked carefully down the alley...",
        "temperature": 0.5,
        "top_p": 0.9
    }
}
message_json = json.dumps(message_data)

for i in range(1):
    channel.basic_publish(exchange='', routing_key='pygmalion_requests', body=message_json)

connection.close()
```

## 模拟

**框架:** 无

**模式:** 无

**模拟内容:** 无

**不模拟内容:** 无

## 测试数据

**测试数据:**
- 硬编码在测试脚本中
- 使用Pygmalion模型示例prompt

**位置:**
- `rabbitmq_test.py` (第19-26行)

## 覆盖

**要求:** 无强制覆盖要求

**查看覆盖:** 无命令

## 测试类型

**手动测试:**
- 手动运行rabbitmq_test.py向队列发送测试消息
- 观察worker日志和结果队列

**集成测试:**
- 需要完整的RabbitMQ环境
- 需要推理服务器可用

**E2E测试:**
- 未实现

## 常见模式

**异步测试:** 不适用

**错误测试:** 手动观察日志

---

*测试分析: 2026-03-30*