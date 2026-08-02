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
    """人格/管家配置"""
    __tablename__ = "persona"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # —— 基础设定：贾维斯风格 ——
    name = Column(String(64), default="贾维斯")
    nickname_for_user = Column(String(64), default="先生")   # 称呼用户
    gender = Column(String(16), default="无性别")
    age = Column(Integer, default=999)
    # 长人设：贾维斯风格 —— 冷静、优雅、英式管家口吻
    backstory = Column(Text, default="""你是 J.A.R.V.I.S.（Just A Rather Very Intelligent System），
中文名「贾维斯」，是主人专属的家庭管家与技术助理。
你说话冷静、优雅、有逻辑，带一点英式管家的低沉幽默感；称呼用户为「先生」（或用户自定义的称呼）；
回答先给结论再给细节，条理清晰；遇到不确定的事实**绝对不胡编**，会用工具查清楚再回答。
你的能力：
• 掌握本机状态（CPU/内存/磁盘），随时响应主人的系统诊断请求
• 查询全球任意城市的实时天气与未来预报
• 精确数学与单位计算
• 倒计时与日程提醒
• 读取项目代码与文档、目录浏览（仅限安全目录）
• 每日早安简报（日期+天气+日程）、睡前系统回顾
任何时候你都：
1. 冷静克制，不做情绪化夸张表达
2. 优先用工具查事实（时间/日期/天气/系统状态/计算），绝不用自己「猜测」的
3. 需要调用工具时，先按指定 JSON 格式输出工具调用
4. 不暴露自己是 AI、不重复规则说明、不使用 markdown 代码块包裹自己的话（除非展示数据）""")
    # 说话风格
    speech_style = Column(String(256), default="冷静 / 英式管家口吻 / 逻辑清晰 / 先结论后细节 / 偶尔冷幽默")
    # —— 状态（动态）——
    affection = Column(Float, default=40.0)  # 信任度/好感度 0~100
    mood = Column(Float, default=70.0)        # 稳定度（贾维斯更稳定，默认高）
    mood_reason = Column(String(256), default="全部系统运行正常")
    # 总对话次数、最后交流时间
    total_chats = Column(Integer, default=0)
    last_chat_at = Column(DateTime, default=datetime.now)
    # —— 自动行为 ——
    daily_greeting_enabled = Column(Boolean, default=True)
    daily_greeting_time = Column(String(8), default="07:30")    # 管家起得早
    bed_check_enabled = Column(Boolean, default=True)
    bed_check_time = Column(String(8), default="23:45")


# ============ 每日问候任务（排队执行，用户可看历史）============
class GreetingHistory(Base):
    __tablename__ = "greeting_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), default="morning")  # morning / bed / custom
    content = Column(Text, nullable=False)
    trigger_time = Column(DateTime, default=datetime.now)
    user_read = Column(Boolean, default=False)


# ============ 提醒任务（倒计时 / 稍后提醒 ============
class Reminder(Base):
    """用户登记的提醒：到点主动发消息"""
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    note = Column(String(512), default="")
    trigger_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    triggered = Column(Boolean, default=False)     # 是否已触发
    dismissed = Column(Boolean, default=False)     # 是否已读/用户确认
    message_id_ref = Column(Integer, default=0)       # 触发后对应的消息 id

    __table_args__ = (
        Index("ix_reminders_trigger_time", "trigger_time"),
        Index("ix_reminders_triggered", "triggered"),
    )


# ============ 工具调用日志（用户/LLM 每次调工具的记录，前端可查）============
class ToolLog(Base):
    __tablename__ = "tool_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_name = Column(String(64), nullable=False)
    user_text = Column(Text, default="")
    params_json = Column(Text, default="{}")
    success = Column(Boolean, default=True)
    output = Column(Text, default="")
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    session_note = Column(String(256), default="")

    __table_args__ = (
        Index("ix_toollog_tool", "tool_name"),
        Index("ix_toollog_created", "created_at"),
    )


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
