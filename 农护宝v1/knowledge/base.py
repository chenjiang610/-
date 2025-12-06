import json
from pathlib import Path
from typing import Dict, Optional, List
from pydantic import BaseModel
from config import KB_PATH
from db import SessionLocal, Knowledge as DbKnowledge

class KnowledgeEntry(BaseModel):
    label: str            # 识别模型的标签（例如 Tomato___Late_blight）
    crop: str             # 作物
    disease: str          # 病虫害（或病害）
    symptoms: str = ""
    description: str = ""
    prevention: str = ""
    source: str = "kb"    # kb / llm
    generated: bool = False

class KnowledgeBase:
    def __init__(self, path: Path = KB_PATH):
        self.path = path
        self.store: Dict[str, KnowledgeEntry] = {}
        self._load()

    def _load(self):
        db = SessionLocal()
        try:
            rows = db.query(DbKnowledge).all()
            self.store = {}
            for r in rows:
                self.store[r.label] = KnowledgeEntry(label=r.label, crop=r.crop, disease=r.disease, symptoms=r.symptoms, description=r.description, prevention=r.prevention, source=r.source, generated=r.generated)
        finally:
            db.close()

    def _save(self):
        db = SessionLocal()
        try:
            for label, entry in self.store.items():
                row = db.query(DbKnowledge).filter_by(label=label).first()
                if not row:
                    db.add(DbKnowledge(label=label, crop=entry.crop, disease=entry.disease, symptoms=entry.symptoms, description=entry.description, prevention=entry.prevention, source=entry.source, generated=entry.generated))
                else:
                    row.crop = entry.crop
                    row.disease = entry.disease
                    row.symptoms = entry.symptoms
                    row.description = entry.description
                    row.prevention = entry.prevention
                    row.source = entry.source
                    row.generated = entry.generated
            db.commit()
        finally:
            db.close()

    def upsert(self, entry: KnowledgeEntry):
        self.store[entry.label] = entry
        self._save()

    def bulk_import(self, entries: List[KnowledgeEntry]):
        for e in entries:
            self.store[e.label] = e
        self._save()

    def replace_all(self, entries: List[KnowledgeEntry]):
        db = SessionLocal()
        try:
            db.query(DbKnowledge).delete()
            db.commit()
        finally:
            db.close()
        self.store = {}
        for e in entries:
            self.store[e.label] = e
        self._save()

    def get(self, label: str) -> Optional[KnowledgeEntry]:
        return self.store.get(label)

    def find_by_crop_or_disease(self, text: str) -> List[KnowledgeEntry]:
        text_l = text.lower()
        results = []
        for e in self.store.values():
            crop_l = (e.crop or '').lower()
            disease_l = (e.disease or '').lower()
            label_l = (e.label or '').lower()
            combo_l = (crop_l + disease_l)
            # 1. 关键字包含 crop/disease/label
            if crop_l in text_l or disease_l in text_l or label_l in text_l:
                results.append(e)
                continue
            # 2. 关键字与 crop+disease 拼接做包含匹配
            if combo_l and combo_l in text_l:
                results.append(e)
                continue
            # 3. 关键字拆分后分别与 crop/disease 匹配
            for kw in text_l.split():
                if kw and (kw in crop_l or kw in disease_l or kw in label_l):
                    results.append(e)
                    break
        return results

    def label_to_crop_disease(self, label: str) -> (str, str):
        # 尝试从知识库获取，如果没有则尝试通过规则拆分
        e = self.get(label)
        if e:
            return e.crop, e.disease
        # 常见 HuggingFace 农业数据集标签样式：Crop___Disease
        if "___" in label:
            parts = label.split("___", 1)
            return parts[0], parts[1]
        # 退化：无法拆分时，病虫害同名
        return "", label
