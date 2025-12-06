import json
import requests
from typing import Optional, Dict, Any, List
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
    
    def test_connection(self) -> bool:
        """测试 Ollama 服务连接"""
        try:
            # 尝试获取模型列表
            url = f"{self.base_url}/api/tags"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = [model.get("name", "") for model in data.get("models", [])]
            print(f"可用模型: {models}")
            return self.model in models
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False

    def generate(self, prompt: str) -> str:
        # 尝试新版本的 chat 端点
        try:
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": 512, "temperature": 0.7}
            }
            resp = requests.post(url, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # 回退到旧版本的 generate 端点
                try:
                    url = f"{self.base_url}/api/generate"
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 512, "temperature": 0.7}
                    }
                    resp = requests.post(url, json=payload, timeout=90)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("response", "")
                except Exception:
                    # 最后的回退：尝试不同的端点格式
                    url = f"{self.base_url}/v1/chat/completions"
                    payload = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "max_tokens": 512,
                        "temperature": 0.7
                    }
                    resp = requests.post(url, json=payload, timeout=90)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                raise

    def chat(self, messages: List[Dict[str, str]]) -> str:
        # 将 messages 转换为单个 prompt
        prompt = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"系统: {content}\n"
            elif role == "user":
                prompt += f"用户: {content}\n"
            elif role == "assistant":
                prompt += f"助手: {content}\n"
        
        # 使用 generate 端点
        return self.generate(prompt)

    def build_diagnosis_json(self, crop: str, disease: str, context: Optional[str] = None) -> Dict[str, Any]:
        prompt = f"""
你是农业专家。请基于作物和病虫害给出结构化诊断，以 JSON 返回：
字段：作物, 病虫害, 症状, 描述, 防治方法。
要求：中文，务实可操作，避免夸张与虚构。
作物：{crop}
病虫害：{disease}
知识库上下文（如有）：{context or "无"}
仅输出 JSON，不要额外文本。
"""
        text = self.generate(prompt).strip()
        # 尝试解析 JSON
        try:
            return json.loads(text)
        except Exception:
            # 宽松提取：如果模型返回含 JSON 的文本，尝试找到第一个 { ... }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
        # 回退
        return {
            "作物": crop,
            "病虫害": disease,
            "症状": "",
            "描述": "",
            "防治方法": ""
        }

    def answer_qa(self, question: str, kb_context: str) -> str:
        messages = [
            {"role": "system", "content": "你是农业病虫害诊断与防治专家，以中文回答。"},
            {"role": "user", "content": f"问题：{question}\n以下是相关知识库内容，可参考但不必逐字复述：\n{kb_context}\n请结合实际给出清晰、简洁、可执行的建议。"}
        ]
        return self.chat(messages)
