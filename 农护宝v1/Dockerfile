FROM python:3.10-slim

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_MODEL=qwen2:latest

WORKDIR /app

# 安装依赖
COPY requirements.txt /app/
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制项目代码
COPY . /app

# 预创建数据目录
RUN python -c "import os; os.makedirs('data', exist_ok=True); os.makedirs('knowledge', exist_ok=True)"

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

