from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import json
from typing import Optional, Dict, Any, List

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    salt = Column(String(64), nullable=False)
    hash = Column(String(128), nullable=False)
    created_at = Column(Integer, nullable=False)
    sessions = relationship("Session", back_populates="user")

class Session(Base):
    __tablename__ = "sessions"
    token = Column(String(128), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(Integer, nullable=False)
    user = relationship("User", back_populates="sessions")

class Diagnostic(Base):
    __tablename__ = "diagnostics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    time = Column(Integer, index=True, nullable=False)
    label = Column(String(128), nullable=False)
    confidence = Column(Float, nullable=False)
    crop = Column(String(128), nullable=False)
    disease = Column(String(128), nullable=False)
    generated = Column(Boolean, default=False)
    predictions = Column(Text, nullable=False)
    report = Column(Text, nullable=False)

class Post(Base):
    __tablename__ = "posts"
    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tags = Column(Text, nullable=False)
    time = Column(Integer, nullable=False)

class Comment(Base):
    __tablename__ = "comments"
    id = Column(String(64), primary_key=True)
    post_id = Column(String(64), ForeignKey("posts.id"), index=True, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    time = Column(Integer, nullable=False)

class Knowledge(Base):
    __tablename__ = "knowledge"
    id = Column(Integer, primary_key=True)
    label = Column(String(256), unique=True, index=True, nullable=False)
    crop = Column(String(128), nullable=False)
    disease = Column(String(128), nullable=False)
    symptoms = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    prevention = Column(Text, nullable=False)
    source = Column(String(32), nullable=False)
    generated = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(bind=engine)

def migrate_from_json():
    init_db()
    session = SessionLocal()
    try:
        users_path = DATA_DIR / "users.json"
        sessions_path = DATA_DIR / "sessions.json"
        diag_path = DATA_DIR / "diagnostics.json"
        posts_path = DATA_DIR / "posts.json"
        comments_path = DATA_DIR / "comments.json"
        kb_path = Path("knowledge") / "knowledge_base.json"

        if users_path.exists():
            data = json.load(open(users_path, "r", encoding="utf-8"))
            for username, u in data.items():
                exists = session.query(User).filter_by(username=username).first()
                if exists:
                    continue
                session.add(User(username=username, salt=u.get("salt",""), hash=u.get("hash",""), created_at=int(u.get("created_at",0) or 0)))
            session.commit()

        if sessions_path.exists():
            data = json.load(open(sessions_path, "r", encoding="utf-8"))
            for token, s in data.items():
                user = session.query(User).filter_by(username=s.get("user")).first()
                if not user:
                    continue
                exists = session.query(Session).filter_by(token=token).first()
                if exists:
                    continue
                session.add(Session(token=token, user_id=user.id, created_at=int(s.get("created_at",0) or 0)))
            session.commit()

        if diag_path.exists():
            data = json.load(open(diag_path, "r", encoding="utf-8"))
            for username, items in (data.items() if isinstance(data, dict) else []):
                user = session.query(User).filter_by(username=username).first()
                if not user:
                    continue
                for r in items or []:
                    exists = session.query(Diagnostic).filter_by(user_id=user.id, time=int(r.get("time",0) or 0)).first()
                    if exists:
                        continue
                    session.add(Diagnostic(user_id=user.id, time=int(r.get("time",0) or 0), label=r.get("label",""), confidence=float(r.get("confidence",0) or 0), crop=r.get("crop",""), disease=r.get("disease",""), generated=bool(r.get("generated",False)), predictions=json.dumps(r.get("predictions",[]), ensure_ascii=False), report=json.dumps(r.get("report",{}), ensure_ascii=False)))
            session.commit()

        if posts_path.exists():
            data = json.load(open(posts_path, "r", encoding="utf-8"))
            for p in data or []:
                exists = session.query(Post).filter_by(id=p.get("id")).first()
                if exists:
                    continue
                user = session.query(User).filter_by(username=p.get("author")).first()
                if not user:
                    continue
                session.add(Post(id=p.get("id"), title=p.get("title",""), content=p.get("content",""), author_id=user.id, tags=json.dumps(p.get("tags",[]), ensure_ascii=False), time=int(p.get("time",0) or 0)))
            session.commit()

        if comments_path.exists():
            data = json.load(open(comments_path, "r", encoding="utf-8"))
            for post_id, items in (data.items() if isinstance(data, dict) else []):
                for c in items or []:
                    exists = session.query(Comment).filter_by(id=c.get("id")).first()
                    if exists:
                        continue
                    user = session.query(User).filter_by(username=c.get("author")).first()
                    if not user:
                        continue
                    session.add(Comment(id=c.get("id"), post_id=post_id, author_id=user.id, content=c.get("content",""), time=int(c.get("time",0) or 0)))
            session.commit()

        if kb_path.exists():
            data = json.load(open(kb_path, "r", encoding="utf-8"))
            for label, e in (data.items() if isinstance(data, dict) else []):
                exists = session.query(Knowledge).filter_by(label=label).first()
                if exists:
                    continue
                session.add(Knowledge(label=label, crop=e.get("crop",""), disease=e.get("disease",""), symptoms=e.get("symptoms",""), description=e.get("description",""), prevention=e.get("prevention",""), source=e.get("source","kb"), generated=bool(e.get("generated", False))))
            session.commit()
    finally:
        session.close()
