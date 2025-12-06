from typing import List
from .base import KnowledgeBase, KnowledgeEntry
from llm.ollama_client import OllamaClient

def generate_entries_for_labels(kb: KnowledgeBase, labels: List[str], llm: OllamaClient):
    for label in labels:
        crop, disease = kb.label_to_crop_disease(label)
        result = llm.build_diagnosis_json(crop or "", disease or "", context=None)
        entry = KnowledgeEntry(
            label=label,
            crop=result.get("作物", crop or ""),
            disease=result.get("病虫害", disease or ""),
            symptoms=result.get("症状", ""),
            description=result.get("描述", ""),
            prevention=result.get("防治方法", ""),
            source="llm",
            generated=True
        )
        kb.upsert(entry)