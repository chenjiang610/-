# 农护宝 v1.0

## 项目简介

农护宝是一个基于深度学习的农作物病虫害识别系统，能够识别38种不同的农作物病虫害，并提供专业的防治建议。

### 主要功能

- 🔍 **智能识别**：支持38种农作物病虫害的自动识别
- 📚 **知识库**：内置详细的农业知识库，提供专业防治方案
- 🤖 **AI诊断**：结合大语言模型生成个性化诊断报告
- 🌐 **Web界面**：简洁易用的网页操作界面
- 📱 **API接口**：完整的RESTful API支持

### 支持的识别类别

包括苹果、蓝莓、樱桃、玉米、葡萄、桃子、辣椒、马铃薯、草莓、番茄等作物的健康状态和常见病虫害。

## 环境要求

- Python 3.8+
- Windows/Linux/macOS
- 至少4GB内存
- 支持CUDA的GPU（可选，用于加速推理）

## 安装配置

### 1. 克隆项目

```bash
git clone <项目地址>
cd 农护宝v1
```

### 2. 创建虚拟环境

**Windows:**
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate
```

**Linux/macOS:**
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置Ollama（大语言模型服务）

#### 安装Ollama

**Windows:**
1. 访问 [Ollama官网](https://ollama.ai) 下载Windows版本
2. 安装后重启终端

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

#### 下载模型

```bash
# 下载中文模型（与后端默认一致）
ollama pull qwen2:latest

# 或下载其他模型
ollama pull qwen2:0.5b
```

#### 启动Ollama服务

```bash
ollama serve
```

### 5. 验证安装

```bash
# 激活虚拟环境（如果还未激活）
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 运行系统验证
python verify_system.py
```

## 启动方法

### 方法一：一键启动（推荐）

```bash
# 激活虚拟环境
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 一键启动服务
python start_server.py
``` 

### 方法二：手动启动

```bash
# 激活虚拟环境
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 启动API服务
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 访问系统

启动成功后，可以通过以下方式访问：

- **Web界面**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 容器部署

### 使用 Docker Compose（推荐）

```bash
docker compose up -d --build
```

- 访问：`http://localhost:8000`
- 默认环境变量：
  - `OLLAMA_BASE_URL=http://host.docker.internal:11434`
  - `OLLAMA_MODEL=qwen2:latest`
- 卷挂载：
  - `./data -> /app/data`（SQLite 数据库）
  - `./knowledge -> /app/knowledge`（知识库导入/导出）
  - `./model -> /app/model`（识别模型权重）

说明：容器内通过 `host.docker.internal:11434` 访问宿主机的 Ollama 服务。如需将 Ollama 也容器化，请将 `OLLAMA_BASE_URL` 改为对应容器服务地址。

### 直接使用 Dockerfile

```bash
docker build -t nonghubao:latest .
docker run -d --name nonghubao -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=qwen2:latest \
  -v %cd%/data:/app/data -v %cd%/knowledge:/app/knowledge -v %cd%/model:/app/model \
  nonghubao:latest
```

Windows PowerShell 使用 `%cd%`；Linux/macOS 请替换为当前路径变量。

## 使用说明

### Web界面使用

1. 打开浏览器访问 http://localhost:8000
2. 上传农作物图片
3. 点击"开始诊断"按钮
4. 查看识别结果和防治建议

### API接口使用

#### 图像识别接口

```bash
curl -X POST "http://localhost:8000/diagnose" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@your_image.jpg"
```

#### 获取支持的标签

```bash
curl "http://localhost:8000/labels"
```

#### 知识库查询

```bash
curl -X POST "http://localhost:8000/qa" \
  -H "Content-Type: application/json" \
  -d '{"question":"苹果黑星病如何防治"}'
```

## 知识库管理

### 导入知识库

```bash
# 导入基础知识库
python import_knowledge.py

# 生成详细知识库
python regenerate_knowledge.py

# 导入详细知识库
python import_detailed_knowledge.py
```

### 数据库版接口

- 导入接口：`POST /kb/import`，上传 JSON；参数：
  - `overwrite=true` 清空并覆盖写入数据库
  - `overwrite=false` 增量写入（同 `label` 更新）
- 问答检索：从数据库知识库检索相关条目，组合上下文并调用本地 LLM。

### 测试知识库

```bash
# 测试知识库功能
python test_knowledge.py

# 测试详细知识库
python test_detailed_knowledge.py
```

## 存储架构

- 运行期存储已由本地 JSON 改为 SQLite 数据库（`data/app.db`）。
- 应用启动时自动迁移旧数据：
  - `data/*.json`（用户、会话、诊断历史、帖子、评论）
  - `knowledge/knowledge_base.json`（知识库条目）
- 迁移完成后系统仅使用数据库；旧 JSON 可删除（若需备份请先保存）。

## LLM 容错

- 若本地 LLM（Ollama）不可用或超时，后端返回“离线模式”的基于知识库的简要建议，前端不再报错。

## 项目结构

### 架构概览

- 后端：`FastAPI` 提供 REST API（`app.py`）
- 数据库：`SQLite` + `SQLAlchemy ORM`（`db.py`）
- 知识库：改为数据库存储，运行时加载到内存检索（`knowledge/base.py`）
- 大模型：通过 `Ollama` 本地服务 HTTP 调用（`llm/ollama_client.py`）
- 前端：原生 JS 单页交互（`frontend/app.js`）
- 图像识别：本地模型加载与推理（`recognition/model_loader.py`）

### 目录说明

- `app.py`：后端主入口，路由与业务逻辑
- `db.py`：数据库引擎、模型、迁移逻辑
- `knowledge/base.py`：知识库服务（现改为读写数据库）
- `llm/ollama_client.py`：Ollama 客户端与生成封装
- `frontend/`：前端资源（`app.js` 交互逻辑）
- `recognition/`：图像识别模型加载与推理
- `data/`：SQLite 数据库文件（`app.db`）与运行数据
- `model/`：本地识别模型权重目录
- `Dockerfile`、`docker-compose.yml`：容器化部署配置

### 关键文件与位置

- 初始化与迁移：`app.py:20–21`、`db.py:61–75`、`db.py:80–152`
- 鉴权与会话：`app.py:389–415`、`app.py:56–80`
- 诊断历史：`app.py:424–458`、`app.py:460–492`、`app.py:494–581`
- 智能分析：`app.py:520–581`
- 社区帖子与评论：`app.py:583–662`
- 问答接口：`app.py:106–129`（即时）、`app.py:130–167`（异步任务）
- LLM 客户端：`llm/ollama_client.py:11–24`（连接检测）、`26–67`（生成）

### 接口一览

- 认证：`POST /auth/register`、`POST /auth/login`、`GET /me`
- 诊断：`POST /diagnose`、`GET /diagnostics/history`、`GET /diagnostics/history/item`、`GET /diagnostics/history/search`
- 分析：`GET /status/analysis`、`GET /diagnostics/insights`
- 问答：`POST /qa`、`POST /qa/task`、`GET /qa/task/{task_id}`
- 社区：`POST /posts`、`GET /posts`、`GET /posts/{post_id}`、`POST /posts/{post_id}/comments`、`GET /posts/{post_id}/comments`
- 知识库：`POST /kb/import`（支持 `overwrite`）

### 配置项

- `config.py`
  - `OLLAMA_BASE_URL`：默认 `http://localhost:11434`
  - `OLLAMA_MODEL`：默认 `qwen2:latest`
  - `KB_PATH`：历史 JSON 路径（现用于导入/备份，不再作为运行存储）

### 故障排除

- Ollama 端口占用：`Only one usage of each socket address` → 已在运行，无需重复 `ollama serve`
- 问答超时：连接或生成超过超时限制 → 后端已加入可用性检测与离线兜底，返回基于知识库的建议而非错误
- 模型响应慢：切换更小模型或减少上下文，配置 `OLLAMA_MODEL`，并在问答中启用 `fast` 以缩短上下文

### 性能建议

- LLM 生成长度限制（客户端已设置），避免长时阻塞
- 数据库读写使用 ORM，后续可按需添加索引（例如 `diagnostics.user_id,time`）以优化查询
