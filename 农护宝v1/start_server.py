#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
农护宝服务启动脚本
"""

import subprocess
import sys
import time
from pathlib import Path

def check_requirements():
    """检查运行环境"""
    print("检查运行环境...")
    
    # 检查知识库文件
    kb_file = Path("knowledge/knowledge_base.json")
    if not kb_file.exists():
        print("❌ 知识库文件不存在，请先运行知识生成脚本")
        return False
    
    # 检查模型文件
    model_file = Path("model/weights/pytorch_model.bin")
    if not model_file.exists():
        print("❌ 模型文件不存在，请检查模型路径")
        return False
    
    print("✓ 环境检查通过")
    return True

def start_server():
    """启动服务"""
    if not check_requirements():
        return
    
    print("\n启动农护宝服务...")
    print("=" * 50)
    print("服务地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    try:
        # 启动uvicorn服务
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    start_server()