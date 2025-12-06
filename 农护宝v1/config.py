import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 本地识别模型权重路径（已存在）
MODEL_WEIGHTS_PATH = BASE_DIR / "model" / "weights"

# Ollama 服务配置
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# 使用实际安装的模型名称
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:latest")

# 知识库路径
KB_DIR = BASE_DIR / "knowledge"
KB_PATH = KB_DIR / "knowledge_base.json"
KB_DIR.mkdir(parents=True, exist_ok=True)