from fastapi import FastAPI, File, UploadFile, Body, Header, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from recognition.model_loader import ModelService
from knowledge.base import KnowledgeBase, KnowledgeEntry
from knowledge.generator import generate_entries_for_labels
from llm.ollama_client import OllamaClient
from pathlib import Path
from db import SessionLocal, init_db, migrate_from_json, User as DbUser, Session as DbSession, Diagnostic as DbDiagnostic, Post as DbPost, Comment as DbComment
from concurrent.futures import ThreadPoolExecutor
import uuid
import hashlib
import secrets
import time
import json

app = FastAPI(title="农护宝 API", version="1.0.0")
init_db()
migrate_from_json()

# 初始化服务
model_service = ModelService()
kb = KnowledgeBase()
llm = OllamaClient()

# 已迁移到数据库（SQLite），不再使用本地 JSON 作为运行期存储

def _hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return {"salt": salt, "hash": digest}

def _verify_password(password: str, salt: str, hashed: str) -> bool:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hashed

def _create_session(username: str) -> str:
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=username).first()
        if not u:
            return ""
        token = secrets.token_urlsafe(32)
        db.add(DbSession(token=token, user_id=u.id, created_at=int(time.time())))
        db.commit()
        return token
    finally:
        db.close()

def _get_user_from_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    token = parts[-1] if parts else authorization
    db = SessionLocal()
    try:
        s = db.query(DbSession).filter_by(token=token).first()
        if not s:
            return None
        u = db.query(DbUser).filter_by(id=s.user_id).first()
        return u.username if u else None
    finally:
        db.close()

def _ensure_state():
    if not hasattr(app.state, "qa_cache"):
        app.state.qa_cache = {}
    if not hasattr(app.state, "qa_tasks"):
        app.state.qa_tasks = {}
    if not hasattr(app.state, "qa_executor"):
        app.state.qa_executor = ThreadPoolExecutor(max_workers=4)

def _append_diag_history(username: str, record: Dict[str, Any]):
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=username).first()
        if not u:
            return
        db.add(DbDiagnostic(user_id=u.id, time=int(record.get("time",0) or 0), label=record.get("label",""), confidence=float(record.get("confidence",0) or 0), crop=record.get("crop",""), disease=record.get("disease",""), generated=bool(record.get("generated",False)), predictions=json.dumps(record.get("predictions",[]), ensure_ascii=False), report=json.dumps(record.get("report",{}), ensure_ascii=False)))
        db.commit()
        count = db.query(DbDiagnostic).filter_by(user_id=u.id).count()
        if count > 500:
            oldest_ids = [d.id for d in db.query(DbDiagnostic).filter_by(user_id=u.id).order_by(DbDiagnostic.time.asc()).limit(count-500).all()]
            if oldest_ids:
                db.query(DbDiagnostic).filter(DbDiagnostic.id.in_(oldest_ids)).delete(synchronize_session=False)
                db.commit()
    finally:
        db.close()

@app.get("/labels")
def labels():
    return {"labels": model_service.get_labels()}

@app.post("/knowledge/import", include_in_schema=False)
async def import_knowledge(entries: List[KnowledgeEntry]):
    kb.bulk_import(entries)
    return {"imported": len(entries)}

@app.post("/knowledge/generate", include_in_schema=False)
def generate_knowledge_for_all_labels():
    labels = model_service.get_labels()
    generate_entries_for_labels(kb, labels, llm)
    return {"generated_count": len(labels)}

@app.post("/qa")
async def qa(question: str = Body(..., embed=True), fast: bool = Body(False, embed=True), authorization: Optional[str] = Header(None)):
    # 简单知识增强：找相关条目组成上下文
    related = kb.find_by_crop_or_disease(question)
    max_ctx = 3 if fast else 5
    context = ""
    for e in related[:max_ctx]:
        context += f"[{e.crop} - {e.disease}] 症状: {e.symptoms}\n描述: {e.description}\n防治: {e.prevention}\n\n"
    context = context[:500]

    cache_key = (question, context[:512])
    _ensure_state()
    def _fallback_answer(q: str, ctx: str) -> str:
        base = "基于知识库的简要建议：\n"
        base += (ctx or "")
        base += "\n综合建议：\n1. 结合症状与描述，先行诊断与排查环境因素\n2. 优先采用知识库中的防治措施，严格执行安全间隔期\n3. 加强通风、控湿与清园，持续监测并记录\n"
        return base
    if cache_key in app.state.qa_cache:
        answer = app.state.qa_cache[cache_key]
    else:
        try:
            if not llm.test_connection():
                raise RuntimeError("llm_unavailable")
            answer = llm.answer_qa(question, kb_context=context)
        except Exception:
            answer = _fallback_answer(question, context)
        if len(app.state.qa_cache) > 1000:
            app.state.qa_cache = {}
        app.state.qa_cache[cache_key] = answer

    # 可选的知识图谱生成（用于前端展示）
    graph = _build_graph_for_query(question)
    return {"answer": answer, "kb_hits": len(related), "graph": graph}

@app.post("/qa/task")
def qa_task_create(question: str = Body(..., embed=True), fast: bool = Body(True, embed=True)):
    _ensure_state()
    related = kb.find_by_crop_or_disease(question)
    max_ctx = 3 if fast else 5
    context = ""
    for e in related[:max_ctx]:
        context += f"[{e.crop} - {e.disease}] 症状: {e.symptoms}\n描述: {e.description}\n防治: {e.prevention}\n\n"
    context = context[:500]
    task_id = uuid.uuid4().hex
    app.state.qa_tasks[task_id] = {"status": "pending", "created_at": int(time.time())}
    def _run():
        try:
            if not llm.test_connection():
                raise RuntimeError("llm_unavailable")
            ans = llm.answer_qa(question, kb_context=context)
            graph = _build_graph_for_query(question)
            app.state.qa_tasks[task_id] = {
                "status": "done",
                "created_at": app.state.qa_tasks[task_id]["created_at"],
                "finished_at": int(time.time()),
                "result": {"answer": ans, "kb_hits": len(related), "graph": graph}
            }
        except Exception as e:
            fallback = "基于知识库的简要建议：\n" + context + "\n综合建议：\n1. 结合症状与描述排查环境因素\n2. 采用知识库防治措施并记录效果\n3. 加强通风控湿与清园，持续监测\n"
            graph = _build_graph_for_query(question)
            app.state.qa_tasks[task_id] = {
                "status": "done",
                "created_at": app.state.qa_tasks[task_id]["created_at"],
                "finished_at": int(time.time()),
                "result": {"answer": fallback + f"\n(离线模式)\n", "kb_hits": len(related), "graph": graph}
            }
    app.state.qa_executor.submit(_run)
    return {"task_id": task_id}

@app.get("/qa/task/{task_id}")
def qa_task_status(task_id: str):
    _ensure_state()
    t = app.state.qa_tasks.get(task_id)
    if not t:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    return t

@app.post("/diagnose")
async def diagnose(image: UploadFile = File(...), top_k: int = 3, authorization: Optional[str] = Header(None)):
    img_bytes = await image.read()
    preds = model_service.predict_top_k(img_bytes, top_k=top_k)
    if not preds:
        return JSONResponse(status_code=400, content={"error": "识别失败或模型无输出"})

    primary = preds[0]
    label = primary["label"]
    score = primary["score"]
    
    # 优先从知识库获取详细信息
    entry = kb.get(label)
    
    if entry:
        # 知识库中有详细信息，直接使用
        report = {
            "label": label,
            "confidence": score,
            "crop": entry.crop,
            "disease": entry.disease,
            "symptoms": entry.symptoms,
            "description": entry.description,
            "prevention": entry.prevention,
            "knowledge_source": entry.source,
            "kb_used": True,
            "generated": entry.generated
        }
        print(f"✓ 使用知识库信息: {entry.crop} - {entry.disease}")
    else:
        # 知识库中没有信息，使用大模型生成
        print(f"⚠ 知识库中未找到 {label}，使用大模型生成")
        
        # 映射作物与病虫害
        crop, disease = kb.label_to_crop_disease(label)
        
        # 让大模型生成诊断信息
        diag = llm.build_diagnosis_json(crop=crop, disease=disease, context=None)
        
        # 数据类型转换函数
        def to_string(value):
            if isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    # 如果是字典列表，提取值并连接
                    return "; ".join([str(v) for item in value for v in item.values()])
                else:
                    # 如果是普通列表，直接连接
                    return "; ".join(str(item) for item in value)
            return str(value) if value else ""
        
        # 创建新的知识条目并保存
        new_entry = KnowledgeEntry(
            label=label,
            crop=to_string(diag.get("作物", crop or "")),
            disease=to_string(diag.get("病虫害", disease or "")),
            symptoms=to_string(diag.get("症状", "")),
            description=to_string(diag.get("描述", "")),
            prevention=to_string(diag.get("防治方法", "")),
            source="llm",
            generated=True
        )
        kb.upsert(new_entry)
        
        report = {
            "label": label,
            "confidence": score,
            "crop": new_entry.crop,
            "disease": new_entry.disease,
            "symptoms": new_entry.symptoms,
            "description": new_entry.description,
            "prevention": new_entry.prevention,
            "knowledge_source": "llm",
            "kb_used": False,
            "generated": True
        }
    
    # 为所有预测结果添加知识信息
    enhanced_predictions = []
    for pred in preds:
        pred_entry = kb.get(pred["label"])
        if pred_entry:
            enhanced_pred = {
                **pred,
                "crop": pred_entry.crop,
                "disease": pred_entry.disease,
                "has_knowledge": True
            }
        else:
            # 简单映射
            crop, disease = kb.label_to_crop_disease(pred["label"])
            enhanced_pred = {
                **pred,
                "crop": crop,
                "disease": disease,
                "has_knowledge": False
            }
        enhanced_predictions.append(enhanced_pred)
    
    # 记录诊断历史（若登录）
    user = _get_user_from_token(authorization)
    if user:
        _append_diag_history(user, {
            "time": int(time.time()),
            "label": report.get("label"),
            "confidence": report.get("confidence"),
            "crop": report.get("crop"),
            "disease": report.get("disease"),
            "generated": report.get("generated"),
            "predictions": enhanced_predictions,
            "report": report
        })

    return {
        "success": True,
        "report": report,
        "predictions": enhanced_predictions,
        "total_predictions": len(preds)
    }

# 知识库状态接口
@app.get("/kb/status")
def kb_status():
    try:
        # 获取知识库统计信息
        total_entries = len(kb.entries) if hasattr(kb, 'entries') else 0
        
        # 获取作物和病害类型数量
        crop_types = set()
        disease_types = set()
        
        if hasattr(kb, 'entries'):
            for entry in kb.entries:
                if hasattr(entry, 'crop') and entry.crop:
                    crop_types.add(entry.crop)
                if hasattr(entry, 'disease') and entry.disease:
                    disease_types.add(entry.disease)
        
        return {
            "total_entries": total_entries,
            "crop_types": len(crop_types),
            "disease_types": len(disease_types),
            "graph_status": "已构建" if total_entries > 0 else "未构建",
            "last_activity": [
                {
                    "message": "知识库系统初始化完成",
                    "time": "刚刚"
                }
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "total_entries": 0,
                "crop_types": 0,
                "disease_types": 0,
                "graph_status": "连接失败",
                "error": str(e)
            }
        )

@app.get("/kb/query")
def kb_query(keyword: str = Query(..., min_length=1, max_length=100, description="要检索的作物/病害关键字"), limit: int = Query(10, ge=1, le=50)):
    keyword = keyword.strip()
    hits = kb.find_by_crop_or_disease(keyword)
    unique_crops, unique_diseases = {}, {}
    for entry in hits:
        if entry.crop:
            unique_crops[entry.crop] = unique_crops.get(entry.crop, 0) + 1
        if entry.disease:
            unique_diseases[entry.disease] = unique_diseases.get(entry.disease, 0) + 1

    entries_payload = [
        {
            "label": entry.label,
            "crop": entry.crop,
            "disease": entry.disease,
            "symptoms": entry.symptoms,
            "description": entry.description,
            "prevention": entry.prevention,
            "source": entry.source,
            "generated": entry.generated
        }
        for entry in hits[:limit]
    ]

    graph = _build_graph_for_query(keyword)

    return {
        "keyword": keyword,
        "total_matches": len(hits),
        "entries": entries_payload,
        "stats": {
            "unique_crops": len(unique_crops),
            "unique_diseases": len(unique_diseases),
            "top_crops": sorted(unique_crops.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_diseases": sorted(unique_diseases.items(), key=lambda x: x[1], reverse=True)[:5]
        },
        "graph": graph
    }

# 认证与用户管理
@app.post("/auth/register")
def register(username: str = Body(..., embed=True), password: str = Body(..., embed=True)):
    db = SessionLocal()
    try:
        exists = db.query(DbUser).filter_by(username=username).first()
        if exists:
            return JSONResponse(status_code=400, content={"error": "用户名已存在"})
        hp = _hash_password(password)
        u = DbUser(username=username, salt=hp["salt"], hash=hp["hash"], created_at=int(time.time()))
        db.add(u)
        db.commit()
        token = _create_session(username)
        return {"token": token, "user": username}
    finally:
        db.close()

@app.post("/auth/login")
def login(username: str = Body(..., embed=True), password: str = Body(..., embed=True)):
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=username).first()
        if not u or not _verify_password(password, u.salt, u.hash):
            return JSONResponse(status_code=401, content={"error": "用户名或密码错误"})
        token = _create_session(username)
        return {"token": token, "user": username}
    finally:
        db.close()

@app.get("/me")
def me(authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    return {"user": user}

@app.get("/diagnostics/history")
def diag_history(authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return {"history": []}
        rows = db.query(DbDiagnostic).filter_by(user_id=u.id).order_by(DbDiagnostic.time.desc()).all()
        hist = []
        for r in rows:
            hist.append({"time": r.time, "label": r.label, "confidence": r.confidence, "crop": r.crop, "disease": r.disease, "generated": r.generated, "predictions": json.loads(r.predictions), "report": json.loads(r.report)})
        return {"history": hist}
    finally:
        db.close()

@app.get("/diagnostics/history/item")
def diag_history_item(time: int = Query(..., description="历史记录的时间戳"), authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return JSONResponse(status_code=404, content={"error": "记录不存在"})
        r = db.query(DbDiagnostic).filter_by(user_id=u.id, time=int(time)).first()
        if not r:
            return JSONResponse(status_code=404, content={"error": "记录不存在"})
        rec = {"time": r.time, "label": r.label, "confidence": r.confidence, "crop": r.crop, "disease": r.disease, "generated": r.generated, "predictions": json.loads(r.predictions), "report": json.loads(r.report)}
        return {"record": rec}
    finally:
        db.close()

@app.get("/diagnostics/history/search")
def diag_history_search(q: str = Query("", min_length=0, max_length=100), authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    keyword = (q or "").strip().lower()
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return {"history": []}
        rows = db.query(DbDiagnostic).filter_by(user_id=u.id).order_by(DbDiagnostic.time.desc()).all()
        hist = []
        for r in rows:
            rec = {"time": r.time, "label": r.label, "confidence": r.confidence, "crop": r.crop, "disease": r.disease, "generated": r.generated, "predictions": json.loads(r.predictions), "report": json.loads(r.report)}
            hist.append(rec)
        if not keyword:
            return {"history": hist[:200]}
        def match(rec: Dict[str, Any]) -> bool:
            fields = []
            fields.append(str(rec.get("label") or ""))
            fields.append(str(rec.get("crop") or ""))
            fields.append(str(rec.get("disease") or ""))
            rep = rec.get("report") or {}
            fields.append(str(rep.get("symptoms") or rep.get("症状") or ""))
            fields.append(str(rep.get("description") or rep.get("描述") or ""))
            fields.append(str(rep.get("prevention") or rep.get("防治方法") or ""))
            text = " \n ".join(fields).lower()
            return keyword in text
        results = [r for r in hist if match(r)]
        return {"history": results[:200]}
    finally:
        db.close()

@app.get("/status/analysis")
def status_analysis(authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return {"summary": {"crops": {}, "diseases": {}}, "trend": []}
        rows = db.query(DbDiagnostic).filter_by(user_id=u.id).order_by(DbDiagnostic.time.asc()).all()
        crops, diseases = {}, {}
        trend = []
        for r in rows[-20:]:
            trend.append({"time": r.time, "label": r.label, "confidence": r.confidence, "crop": r.crop, "disease": r.disease, "generated": r.generated})
        for r in rows:
            c = (r.crop or "").strip()
            d = (r.disease or "").strip()
            if c:
                crops[c] = crops.get(c, 0) + 1
            if d:
                diseases[d] = diseases.get(d, 0) + 1
        return {"summary": {"crops": crops, "diseases": diseases}, "trend": trend}
    finally:
        db.close()

@app.get("/diagnostics/insights")
def diagnostics_insights(authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return {"insights": "暂无历史记录，无法生成分析", "summary": {"records": 0}}
        rows = db.query(DbDiagnostic).filter_by(user_id=u.id).order_by(DbDiagnostic.time.desc()).limit(50).all()
        hist = []
        for r in rows:
            hist.append({"time": r.time, "label": r.label, "confidence": r.confidence, "crop": r.crop, "disease": r.disease, "generated": r.generated})
        if not hist:
            return {"insights": "暂无历史记录，无法生成分析", "summary": {"records": 0}}
        crops, diseases = {}, {}
        for r in hist:
            c = (r.get("crop") or "").strip()
            d = (r.get("disease") or "").strip()
            if c:
                crops[c] = crops.get(c, 0) + 1
            if d:
                diseases[d] = diseases.get(d, 0) + 1
        top_crops = sorted(crops.items(), key=lambda x: x[1], reverse=True)[:3]
        top_diseases = sorted(diseases.items(), key=lambda x: x[1], reverse=True)[:5]
        summary = {"records": len(hist), "top_crops": top_crops, "top_diseases": top_diseases}
        ctx = "历史诊断概览：\n"
        ctx += f"诊断次数：{len(hist)}\n"
        ctx += f"主要作物：{', '.join([f'{c}({n})' for c, n in top_crops]) or '无'}\n"
        ctx += f"主要病害：{', '.join([f'{d}({n})' for d, n in top_diseases]) or '无'}\n"
        prompt = f"""
你是农业专家。基于以下历史概览，给出中文的综合分析：
包含：
1) 历史概览与主要风险点
2) 整体作物长势评价（结合高频作物与病害）
3) 未来可能遇到的问题（按主要作物分组）
4) 防治建议（通用与针对重点病害的具体措施）
5) 近期工作建议与监测要点
要求简洁、可执行，避免夸张与虚构。
{ctx}
"""
        try:
            if not llm.test_connection():
                raise RuntimeError("llm_unavailable")
            text = llm.generate(prompt).strip()
            return {"insights": text, "summary": summary}
        except Exception:
            lines = []
            lines.append("综合分析（离线模式）：")
            lines.append(f"诊断次数：{summary['records']}")
            tc = ", ".join([f"{c}({n})" for c, n in summary['top_crops']]) or "无"
            td = ", ".join([f"{d}({n})" for d, n in summary['top_diseases']]) or "无"
            lines.append(f"主要作物：{tc}")
            lines.append(f"主要病害：{td}")
            lines.append("整体长势：高频病害提示需加强田间巡查与环境管理")
            lines.append("未来问题：重点作物在高温高湿时段可能出现病害加重")
            lines.append("防治建议：1) 加强通风与排水 2) 轮作与清园 3) 选用针对性药剂并遵循安全间隔期")
            lines.append("近期工作：建立每周巡查台账，记录症状变化与处理结果")
            return {"insights": "\n".join(lines), "summary": summary, "offline": True}
    finally:
        db.close()

@app.post("/posts")
def create_post(title: str = Body(..., embed=True), content: str = Body(..., embed=True), tags: List[str] = Body([], embed=True), authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return JSONResponse(status_code=401, content={"error": "未登录"})
        pid = uuid.uuid4().hex
        db.add(DbPost(id=pid, title=title, content=content, author_id=u.id, tags=json.dumps(tags or [], ensure_ascii=False), time=int(time.time())))
        db.commit()
        return {"post": {"id": pid, "title": title, "content": content, "author": user, "tags": tags or [], "time": int(time.time())}}
    finally:
        db.close()

@app.get("/posts")
def list_posts():
    db = SessionLocal()
    try:
        rows = db.query(DbPost).order_by(DbPost.time.desc()).all()
        posts = []
        for p in rows:
            author = db.query(DbUser).filter_by(id=p.author_id).first()
            posts.append({"id": p.id, "title": p.title, "content": p.content, "author": author.username if author else "", "tags": json.loads(p.tags), "time": p.time})
        return {"posts": posts}
    finally:
        db.close()

@app.get("/posts/{post_id}")
def get_post(post_id: str):
    db = SessionLocal()
    try:
        p = db.query(DbPost).filter_by(id=post_id).first()
        if not p:
            return JSONResponse(status_code=404, content={"error": "帖子不存在"})
        author = db.query(DbUser).filter_by(id=p.author_id).first()
        post = {"id": p.id, "title": p.title, "content": p.content, "author": author.username if author else "", "tags": json.loads(p.tags), "time": p.time}
        rows = db.query(DbComment).filter_by(post_id=post_id).order_by(DbComment.time.asc()).all()
        clist = []
        for c in rows:
            au = db.query(DbUser).filter_by(id=c.author_id).first()
            clist.append({"id": c.id, "post_id": c.post_id, "author": au.username if au else "", "content": c.content, "time": c.time})
        return {"post": post, "comments": clist}
    finally:
        db.close()

@app.post("/posts/{post_id}/comments")
def add_comment(post_id: str, content: str = Body(..., embed=True), authorization: Optional[str] = Header(None)):
    user = _get_user_from_token(authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    db = SessionLocal()
    try:
        p = db.query(DbPost).filter_by(id=post_id).first()
        if not p:
            return JSONResponse(status_code=404, content={"error": "帖子不存在"})
        u = db.query(DbUser).filter_by(username=user).first()
        if not u:
            return JSONResponse(status_code=401, content={"error": "未登录"})
        cid = uuid.uuid4().hex
        db.add(DbComment(id=cid, post_id=post_id, author_id=u.id, content=content, time=int(time.time())))
        db.commit()
        return {"comment": {"id": cid, "post_id": post_id, "author": user, "content": content, "time": int(time.time())}}
    finally:
        db.close()

@app.get("/posts/{post_id}/comments")
def list_comments(post_id: str):
    db = SessionLocal()
    try:
        rows = db.query(DbComment).filter_by(post_id=post_id).order_by(DbComment.time.asc()).all()
        clist = []
        for c in rows:
            au = db.query(DbUser).filter_by(id=c.author_id).first()
            clist.append({"id": c.id, "post_id": c.post_id, "author": au.username if au else "", "content": c.content, "time": c.time})
        return {"comments": clist}
    finally:
        db.close()

# 知识库管理与知识图谱
@app.post("/kb/import")
async def kb_import(file: UploadFile = File(...), overwrite: bool = Body(True), validate: bool = Body(True)):
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        entries = []
        for label, e in data.items():
            entries.append(KnowledgeEntry(label=label, crop=e.get("crop", ""), disease=e.get("disease", ""), symptoms=e.get("symptoms", ""), description=e.get("description", ""), prevention=e.get("prevention", ""), source=e.get("source", "kb"), generated=bool(e.get("generated", False))))
        if overwrite:
            kb.replace_all(entries)
        else:
            kb.bulk_import(entries)
        return {"message": f"导入{len(entries)}条"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


def _build_graph_for_query(text: str) -> Dict[str, Any]:
    hits = kb.find_by_crop_or_disease(text)
    nodes, edges = [], []
    node_map = {}
    def add_node(name: str, ntype: str):
        key = f"{ntype}:{name}"
        if name and key not in node_map:
            node_map[key] = len(nodes)
            nodes.append({"id": key, "label": name, "type": ntype})
        return node_map.get(key)
    for e in hits[:20]:
        ci = add_node(e.crop, "crop")
        di = add_node(e.disease, "disease")
        if ci is not None and di is not None:
            edges.append({"source": nodes[ci]["id"], "target": nodes[di]["id"], "label": "疾病关联"})
    return {"nodes": nodes, "edges": edges, "count": len(hits)}

@app.get("/kb/graph")
def kb_graph(query: str):
    return _build_graph_for_query(query)

# 功能页面路由 - 必须放在API路由之后
@app.get("/diagnose")
def diagnose_page():
    return FileResponse("frontend/diagnose.html")

@app.get("/qa")
def qa_page():
    return FileResponse("frontend/qa.html")

@app.get("/kb")
def kb_page():
    return FileResponse("frontend/kb.html")

@app.get("/community")
def community_page():
    return FileResponse("frontend/community.html")

# 挂载前端静态资源
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 首页返回前端页面
@app.get("/")
def index():
    return FileResponse("frontend/index.html")
