import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification
from typing import List, Dict
from utils.image_utils import load_image_from_bytes
from config import MODEL_WEIGHTS_PATH

class ModelService:
    def __init__(self):
        self.processor = AutoImageProcessor.from_pretrained(str(MODEL_WEIGHTS_PATH))
        self.model = AutoModelForImageClassification.from_pretrained(str(MODEL_WEIGHTS_PATH))
        self.id2label = self.model.config.id2label if hasattr(self.model.config, "id2label") else None

    def get_labels(self) -> List[str]:
        if self.id2label:
            # id2label: { "0": "Tomato___Late_blight", ... }
            # 统一输出 label 列表
            labels = []
            for i in range(len(self.id2label)):
                # 尝试多种键格式
                label = None
                for key_format in [str(i), i]:
                    if key_format in self.id2label:
                        label = self.id2label[key_format]
                        break
                if label:
                    labels.append(label)
                else:
                    labels.append(f"Unknown_Class_{i}")
            return labels
        return []

    def predict_top_k(self, img_bytes: bytes, top_k: int = 3) -> List[Dict]:
        image = load_image_from_bytes(img_bytes)
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).squeeze(0)
            topk = torch.topk(probs, k=min(top_k, probs.shape[-1]))
            results = []
            for score, idx in zip(topk.values.tolist(), topk.indices.tolist()):
                # 更安全的标签获取方式
                if self.id2label:
                    # 尝试多种键格式
                    label = None
                    for key_format in [str(idx), idx, int(idx)]:
                        if key_format in self.id2label:
                            label = self.id2label[key_format]
                            break
                    if label is None:
                        print(f"警告: 找不到索引 {idx} 对应的标签，可用键: {list(self.id2label.keys())}")
                        label = f"Unknown_Class_{idx}"
                else:
                    label = f"Class_{idx}"
                results.append({"label": label, "score": score})
            return results