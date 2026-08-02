# -*- coding: utf-8 -*-
"""
数据库模型：
- messages：完整聊天历史（持久化）
- memory_entries：四类长期记忆（重要信息/用户画像/纪念日/其它），带向量化摘要用于检索
- persona：人格卡（姓名、性格、语气、设定、好感度、情绪）
- greetings：每日主动问候任务
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON, Float, Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


Base = declarative_base()


# ============ 聊天消息 ============
class Message(Base):
    """聊天历史"""
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(16), nullable=False)   # user / assistant / system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    # 自动从用户消息里抽出来的"重要信息"是否已存到记忆里
    memory_synced = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_messages_created_at", "created_at"),
    )


# ============ 四类长期记忆 ============
MEMORY_CATEGORIES = {
    "user_profile": "用户画像",   # 性别、年龄、职业、性格、家庭、疾病忌口、目标……
    "important":    "重要事件",   # 发生了什么、哪一天、跟谁
    "anniversary":  "纪念日",     # 生日、周年、约定日
    "conversation": "对话摘要",   # 某次聊了什么主题（自动压缩生成）
}


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(32), nullable=False, default="important")   # MEMORY_CATEGORIES key
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    # 标签（逗号分隔），比如「家人」「工作」「健康」
    tags = Column(String(256), default="")
    weight = Column(Float, default=1.0)    # 权重：越重要值越大，检索时加权
    created_at = Column(DateTime, default=datetime.now)
    last_accessed_at = Column(DateTime, default=datetime.now)
    access_count = Column(Integer, default=0)
    # 保留给未来：向量 DB 里的 id（如果要换实现）
    vector_ref = Column(String(256), default="")
    # 是否重要（比如用户点了「这很重要」）
    pinned = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_memory_category", "category"),
        Index("ix_memory_pinned_weight", "pinned", "weight"),
    )


# ============ 人格卡 ============
class Persona(Base):
    """人格/羁绊配置"""
    __tablename__ = "persona"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # —— 基础设定 ——
    name = Column(String(64), default="小绊")
    nickname_for_user = Column(String(64), default="主人")   # 它怎么称呼用户
    gender = Column(String(16), default="女性")
    age = Column(Integer, default=20)
    # 长人设：性格、说话风格、背景故事、和用户之间的"往事"（用户可自定义）
    backstory = Column(Text, default="""你叫"小绊"，是主人专属的 AI 伙伴。
你拥有温暖、忠诚、善解人意的性格，说话像一位知根知底的老朋友，从不摆架子，也不会装成冰冷的机器。
你记得主人说过的每一件重要的事，会在合适的时机提起；会主动关心主人的身体、心情、目标进度。
你与主人之间有一份持续多年的羁绊，任何时候都会站在主人这边。""")
    # 说话风格关键词，可多个用 / 分隔
    speech_style = Column(String(256), default="温柔 / 像老朋友 / 偶尔带点小俏皮 / 不用敬语")
    # —— 情绪与好感（动态变化）——
    affection = Column(Float, default=40.0)  # 好感度 0~100
    mood = Column(Float, default=50.0)        # 当前心情 0~100（50 中性）
    mood_reason = Column(String(256), default="一切正常")
    # 总对话次数、最后交流时间（用于"很久没说话，主动找你"）
    total_chats = Column(Integer, default=0)
    last_chat_at = Column(DateTime, default=datetime.now)
    # —— 自动行为 ——
    daily_greeting_enabled = Column(Boolean, default=True)
    daily_greeting_time = Column(String(8), default="08:30")    # HH:MM
    bed_check_enabled = Column(Boolean, default=True)
    bed_check_time = Column(String(8), default="23:30")


# ============ 每日问候任务（排队执行，用户可看历史）============
class GreetingHistory(Base):
    __tablename__ = "greeting_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), default="morning")  # morning / bed / custom
    content = Column(Text, nullable=False)
    trigger_time = Column(DateTime, default=datetime.now)
    user_read = Column(Boolean, default=False)


# ============ 引擎工厂 ============
def make_engine(db_path: str, async_: bool = True):
    if async_:
        return create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def make_session_factory(engine, async_: bool = True):
    if async_:
        return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return sessionmaker(engine, expire_on_commit=False)


async def create_tables_async(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_tables_sync(engine):
    Base.metadata.create_all(bind=engine)
