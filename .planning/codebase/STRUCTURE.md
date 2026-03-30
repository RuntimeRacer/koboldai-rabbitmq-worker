# 代码库结构

**分析日期:** 2026-03-30

## 目录布局

```
koboldai-rabbitmq-worker/
├── .planning/
│   └── codebase/          # 规划文档目录
├── .git/                  # Git版本控制
├── .gitignore             # Git忽略配置
├── Dockerfile             # Docker镜像构建
├── docker-compose.yml     # Docker Compose配置
├── LICENSE                # AGPL许可证
├── README.md              # 项目说明文档
├── rabbitmq.py            # 主程序文件
├── rabbitmq_test.py       # 测试脚本
├── requirements.txt       # Python依赖
└── run.sh                 # 运行脚本
```

## 目录用途

**项目根目录:**
- 目的：存放所有项目文件和配置
- 包含：源代码、Docker配置、文档

**源代码目录:**
- 目的：项目无子目录，所有代码在根目录
- 关键文件：
  - `rabbitmq.py`：主程序（286行）
  - `rabbitmq_test.py`：测试脚本（32行）

**配置目录:**
- 目的：Docker和环境配置
- 文件：
  - `Dockerfile`：Python 3.9-slim镜像
  - `docker-compose.yml`：RabbitMQ服务
  - `requirements.txt`：Python依赖
  - `.gitignore`：忽略文件模式

## 关键文件位置

**入口点:**
- `rabbitmq.py`：主程序入口，通过命令行参数运行
- `rabbitmq_test.py`：测试消息发送入口

**配置:**
- `Dockerfile`：容器化配置，环境变量定义
- `docker-compose.yml`：RabbitMQ服务配置
- `run.sh`：Shell运行脚本

**核心逻辑:**
- `rabbitmq.py`：
  - RabbitMQWorker类（第34-242行）
  - run方法（第81-110行）
  - handle_prompt_message方法（第129-215行）
  - shutdown方法（第216-242行）

## 命名约定

**文件:**
- snake_case：rabbitmq.py, rabbitmq_test.py

**类:**
- PascalCase：RabbitMQWorker

**函数:**
- snake_case：ack_message, nack_message, handle_prompt_message

**变量:**
- snake_case：rabbitmq_user, polling_connection, message_id

## 新增代码位置

**新功能:**
- 主代码：`rabbitmq.py`（项目结构简单，所有代码在同一文件）

**测试:**
- 测试脚本：`rabbitmq_test.py`（简单测试消息发送）
- 单元测试：项目目前无正式单元测试框架

**工具函数:**
- 共享帮助：应在`rabbitmq.py`中添加

## 特殊目录

**.git/：**
- 目的：Git版本控制元数据
- 生成：是
- 提交：否（自动生成）

**.planning/codebase/：**
- 目的：存放代码库分析文档
- 生成：是
- 提交：建议

---

*结构分析: 2026-03-30*