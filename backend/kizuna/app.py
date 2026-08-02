# -*- coding: utf-8 -*-
"""
FastAPI 应用 + REST 路由
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Optional

# 尽早加载 .env（在 os.environ 读取之前）
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

from fastapi import FastAPI, Depends, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .db import (
    Message, MemoryEntry, Persona, GreetingHistory, Reminder, ToolLog,
    make_engine, make_session_factory, create_tables_async,
    MEMORY_CATEGORIES,
)
from .llm import ChatLLM, LLMConfig, SUPPORTED_PROVIDERS
from .memory import MemoryStore
from .brain import Brain


DEFAULT_DATA_DIR = os.environ.get("KIZUNA_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))


# ============ 依赖注入 ============
_ENGINE = None
_SESSION_FACTORY = None
_BRAIN: Optional[Brain] = None
_MEMORY_STORE: Optional[MemoryStore] = None
_LLM: Optional[ChatLLM] = None


async def get_db() -> AsyncSession:
    if _SESSION_FACTORY is None:
        raise RuntimeError("未初始化")
    async with _SESSION_FACTORY() as s:
        yield s


def get_brain() -> Brain:
    if _BRAIN is None:
        raise RuntimeError("Brain 未初始化，请检查 LLM 配置")
    return _BRAIN


def get_memory() -> MemoryStore:
    if _MEMORY_STORE is None:
        raise RuntimeError("MemoryStore 未初始化")
    return _MEMORY_STORE


# ============ 初始化 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ENGINE, _SESSION_FACTORY, _MEMORY_STORE, _LLM, _BRAIN

    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
    db_path = os.path.join(DEFAULT_DATA_DIR, "kizuna.sqlite3")
    _ENGINE = make_engine(db_path, async_=True)
    _SESSION_FACTORY = make_session_factory(_ENGINE, async_=True)
    await create_tables_async(_ENGINE)

    # Memory + LLM + Brain
    _MEMORY_STORE = MemoryStore(data_dir=DEFAULT_DATA_DIR)

    # 从环境变量 / env 读取 LLM 配置
    provider = os.environ.get("KIZUNA_LLM_PROVIDER", "zhipu")
    cfg = LLMConfig(provider=provider)
    try:
        _LLM = ChatLLM(cfg)
        # 试一下
        print(f"[KIZUNA] LLM 已初始化: provider={provider}, model={_LLM.model}, base={_LLM.base}")
    except Exception as e:
        print(f"[KIZUNA] ⚠ LLM 初始化失败({e})。聊天接口会报错，完成设置后再聊。")
        _LLM = None

    _BRAIN = Brain(llm=_LLM, memory_store=_MEMORY_STORE) if _LLM else None

    # 定时任务（APScheduler）：早安 / 睡前问候 + 纪念日 + 久未联系
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        sched = AsyncIOScheduler(timezone=os.environ.get("TZ", "Asia/Shanghai"))

        async def run_scheduled_greeting(type_: str, cfg_getter):
            sess = _SESSION_FACTORY()
            try:
                # 先读 persona 看看开关
                p = (await sess.execute(select(Persona).order_by(Persona.id.asc()))).scalars().first()
                if not p:
                    return
                enabled = cfg_getter(p)
                if not enabled:
                    return
                if not _BRAIN:
                    return
                text = await _BRAIN.trigger_greeting(sess, type_)
                if text:
                    # 写入 GreetingHistory 已在 trigger_greeting 内完成
                    print(f"[KIZUNA] 定时问候({type_}): {text[:40]}…")
            except Exception as e:
                print(f"[KIZUNA] 定时问候失败: {e}")
            finally:
                await sess.close()

        # 每小时轮询，看看需不需要触发早安/睡前（用户可自定义时间）
        async def every_hour_check():
            now = datetime.now()
            sess = _SESSION_FACTORY()
            try:
                p = (await sess.execute(select(Persona).order_by(Persona.id.asc()))).scalars().first()
                if not p or not _BRAIN:
                    return
                if p.daily_greeting_enabled and now.strftime("%H:%M") == p.daily_greeting_time:
                    await _BRAIN.trigger_greeting(sess, "morning")
                if p.bed_check_enabled and now.strftime("%H:%M") == p.bed_check_time:
                    await _BRAIN.trigger_greeting(sess, "bed")
            except Exception as e:
                print(f"[KIZUNA] 轮询问候失败: {e}")
            finally:
                await sess.close()

        async def every_day_miss_check():
            """每天一次：如果超过 7 天没说话，主动联系"""
            sess = _SESSION_FACTORY()
            try:
                p = (await sess.execute(select(Persona).order_by(Persona.id.asc()))).scalars().first()
                if not p or not _BRAIN:
                    return
                days = (datetime.now() - p.last_chat_at).days
                if days >= 7:
                    await _BRAIN.trigger_greeting(sess, "miss")
            except Exception as e:
                print(f"[KIZUNA] miss check 失败: {e}")
            finally:
                await sess.close()

        # 每 30 秒轮询提醒（倒计时是否到点
        async def every_30s_reminder_poll():
            sess = _SESSION_FACTORY()
            try:
                if _BRAIN:
                    n = await _BRAIN.poll_reminders(sess)
                    if n:
                        print(f"[JARVIS] 已触发 {n} 条到点提醒")
            except Exception as e:
                print(f"[JARVIS] 提醒轮询失败: {e}")
            finally:
                await sess.close()

        sched.add_job(every_hour_check, "cron", minute=0, id="every_hour")
        sched.add_job(every_day_miss_check, "cron", hour=20, minute=0, id="every_day")
        sched.add_job(every_30s_reminder_poll, "interval", seconds=30, id="every_30s_reminder")
        sched.start()
        app.state.scheduler = sched
    except Exception as e:
        print(f"[KIZUNA] APScheduler 未启动（定时问候将不可用）: {e}")

    yield
    # shutdown
    if getattr(app.state, "scheduler", None):
        try:
            app.state.scheduler.shutdown(wait=False)
        except Exception:
            pass
    if _ENGINE:
        await _ENGINE.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kizuna AI · 羁绊 AI",
        description="有记忆、有人格、懂感情的 AI 伙伴",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 注册路由 ----
    register_routes(app)

    # ---- 静态文件：前端（在 build 后挂载）----
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


# ============ 路由 ============
def register_routes(app: FastAPI):
    # =========================================================
    # 1. 基础状态接口
    # =========================================================
    @app.get("/api/health", tags=["系统"])
    async def health():
        """检测系统状态"""
        persona_ok = False
        if _SESSION_FACTORY:
            try:
                async with _SESSION_FACTORY() as s:
                    r = (await s.execute(select(Persona).limit(1))).scalars().first()
                    persona_ok = bool(r)
            except Exception:
                pass
        return {
            "ok": True,
            "llm_initialized": _LLM is not None,
            "llm_provider": _LLM.provider_label if _LLM else None,
            "llm_model": _LLM.model if _LLM else None,
            "persona_initialized": persona_ok,
            "data_dir": DEFAULT_DATA_DIR,
        }

    @app.get("/api/providers", tags=["配置"])
    async def list_providers():
        """列出支持的 LLM 供应商"""
        return SUPPORTED_PROVIDERS

    class LLMSaveConfig(BaseModel):
        provider: str
        api_key: str = ""
        base_url: str = ""
        model: str = ""
        temperature: float = 0.75
        max_tokens: int = 1200

    @app.post("/api/config/llm", tags=["配置"])
    async def save_llm_config(cfg: LLMSaveConfig):
        """更新 LLM 配置（立刻生效）；同时写入 .env 文件作为持久化"""
        global _LLM, _BRAIN
        if cfg.provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(400, f"不支持的供应商: {cfg.provider}")
        llm_cfg = LLMConfig(
            provider=cfg.provider, api_key=cfg.api_key, base_url=cfg.base_url,
            model=cfg.model, temperature=cfg.temperature, max_tokens=cfg.max_tokens,
        )
        new_llm = ChatLLM(llm_cfg)

        # 写入 env 文件
        env_path = os.path.join(DEFAULT_DATA_DIR, "..", ".env")
        try:
            lines = []
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            kv = {
                "KIZUNA_LLM_PROVIDER": cfg.provider,
                "KIZUNA_LLM_API_KEY": cfg.api_key,
                "KIZUNA_LLM_BASE": cfg.base_url,
                "KIZUNA_LLM_MODEL": cfg.model,
            }
            new_lines = []
            keys_seen = set()
            for line in lines:
                if line.startswith("#") or "=" not in line:
                    new_lines.append(line); continue
                k = line.split("=", 1)[0].strip()
                if k in kv:
                    new_lines.append(f"{k}={kv[k]}")
                    keys_seen.add(k)
                else:
                    new_lines.append(line)
            for k, v in kv.items():
                if k not in keys_seen and v:
                    new_lines.append(f"{k}={v}")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        except Exception:
            pass

        _LLM = new_llm
        if _BRAIN:
            _BRAIN.llm = new_llm
        else:
            _BRAIN = Brain(llm=new_llm, memory_store=get_memory())
        return {"ok": True, "provider": new_llm.provider_label, "model": new_llm.model, "base": new_llm.base}

    # =========================================================
    # 2. 聊天 API
    # =========================================================
    class ChatReq(BaseModel):
        text: str = Field(..., min_length=1, max_length=4000)

    @app.post("/api/chat", tags=["聊天"])
    async def chat(
        req: ChatReq,
        db: AsyncSession = Depends(get_db),
        brain: Brain = Depends(get_brain),
    ):
        try:
            result = await brain.chat(db, req.text)
        except Exception as e:
            raise HTTPException(500, f"聊天失败: {e}")
        return {
            "reply": result.reply,
            "affection_delta": round(result.affection_delta, 2),
            "mood_delta": round(result.mood_delta, 2),
            "memories_used": result.memories_used,
            "new_memories_saved": result.new_memories_saved,
            "tool_used": result.tool_used,
            "tool_success": result.tool_success,
            "tool_display": result.tool_display,
            "reminders_added": result.reminders_added,
        }

    @app.get("/api/chat/history", tags=["聊天"])
    async def chat_history(
        limit: int = Query(50, ge=1, le=500),
        before_id: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        q = select(Message).order_by(desc(Message.id))
        if before_id:
            q = q.where(Message.id < before_id)
        rows = (await db.execute(q.limit(limit))).scalars().all()
        rows.reverse()
        return [{
            "id": m.id, "role": m.role, "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "memory_synced": m.memory_synced,
        } for m in rows]

    # =========================================================
    # 3. 人格/好感设置
    # =========================================================
    @app.get("/api/persona", tags=["人格"])
    async def get_persona(db: AsyncSession = Depends(get_db)):
        p = await Brain.get_persona(db)
        await db.commit()
        return {
            "id": p.id,
            "name": p.name,
            "nickname_for_user": p.nickname_for_user,
            "gender": p.gender,
            "age": p.age,
            "backstory": p.backstory,
            "speech_style": p.speech_style,
            "affection": p.affection,
            "mood": p.mood,
            "mood_reason": p.mood_reason,
            "total_chats": p.total_chats,
            "last_chat_at": p.last_chat_at.isoformat() if p.last_chat_at else None,
            "daily_greeting_enabled": p.daily_greeting_enabled,
            "daily_greeting_time": p.daily_greeting_time,
            "bed_check_enabled": p.bed_check_enabled,
            "bed_check_time": p.bed_check_time,
        }

    class PersonaPatch(BaseModel):
        name: Optional[str] = None
        nickname_for_user: Optional[str] = None
        gender: Optional[str] = None
        age: Optional[int] = None
        backstory: Optional[str] = None
        speech_style: Optional[str] = None
        daily_greeting_enabled: Optional[bool] = None
        daily_greeting_time: Optional[str] = None
        bed_check_enabled: Optional[bool] = None
        bed_check_time: Optional[str] = None

    @app.patch("/api/persona", tags=["人格"])
    async def patch_persona(p: PersonaPatch, db: AsyncSession = Depends(get_db)):
        current = await Brain.get_persona(db)
        for k, v in p.model_dump(exclude_unset=True).items():
            if hasattr(current, k) and v is not None:
                setattr(current, k, v)
        await db.commit()
        return await get_persona(db)

    # =========================================================
    # 4. 记忆管理
    # =========================================================
    @app.get("/api/memory", tags=["记忆"])
    async def list_memory(
        category: str = "",
        q: str = "",
        db: AsyncSession = Depends(get_db),
    ):
        ms = get_memory()
        if q:
            mems = await ms.search(db, q, top_k=30, category=category or None)
            return [{
                "id": m.id, "category": m.category,
                "category_label": MEMORY_CATEGORIES.get(m.category, m.category),
                "title": m.title, "content": m.content,
                "tags": m.tags, "score": m.score, "pinned": m.pinned,
            } for m in mems]
        rows = await ms.list_all(db, category=category or None)
        return [{
            "id": r.id, "category": r.category,
            "category_label": MEMORY_CATEGORIES.get(r.category, r.category),
            "title": r.title, "content": r.content, "tags": r.tags,
            "weight": r.weight, "pinned": r.pinned,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "access_count": r.access_count,
        } for r in rows]

    class MemoryAdd(BaseModel):
        category: str = "important"
        title: str = Field(..., min_length=1, max_length=200)
        content: str = Field(..., min_length=1, max_length=4000)
        tags: str = ""
        weight: float = 5.0
        pinned: bool = False

    @app.post("/api/memory", tags=["记忆"])
    async def add_memory(m: MemoryAdd, db: AsyncSession = Depends(get_db)):
        if m.category not in MEMORY_CATEGORIES:
            raise HTTPException(400, "category 非法")
        ms = get_memory()
        entry = await ms.add(db, category=m.category, title=m.title, content=m.content, tags=m.tags, weight=m.weight, pinned=m.pinned)
        await db.commit()
        return {"ok": True, "id": entry.id}

    @app.patch("/api/memory/{mid}", tags=["记忆"])
    async def patch_memory(mid: int, m: MemoryAdd, db: AsyncSession = Depends(get_db)):
        entry = await db.get(MemoryEntry, mid)
        if not entry:
            raise HTTPException(404, "记忆不存在")
        if m.category not in MEMORY_CATEGORIES:
            raise HTTPException(400, "category 非法")
        entry.category = m.category; entry.title = m.title; entry.content = m.content
        entry.tags = m.tags; entry.weight = m.weight; entry.pinned = m.pinned
        # 同步向量库
        ms = get_memory()
        ms._upsert_vector(entry.id, entry.title, entry.content, entry.tags, entry.category)
        await db.commit()
        return {"ok": True}

    @app.delete("/api/memory/{mid}", tags=["记忆"])
    async def delete_memory(mid: int, db: AsyncSession = Depends(get_db)):
        await get_memory().delete(db, mid)
        await db.commit()
        return {"ok": True}

    @app.get("/api/memory/categories", tags=["记忆"])
    def memory_categories():
        return MEMORY_CATEGORIES

    # =========================================================
    # 5. 主动问候（触发 / 看历史）
    # =========================================================
    @app.post("/api/greeting/trigger/{type_}", tags=["问候"])
    async def trigger_greeting(
        type_: str,
        db: AsyncSession = Depends(get_db),
        brain: Brain = Depends(get_brain),
    ):
        if type_ not in ("morning", "bed", "anniversary", "miss", "custom"):
            raise HTTPException(400, "type 非法")
        text = await brain.trigger_greeting(db, type_)
        return {"ok": bool(text), "content": text}

    @app.get("/api/greeting/history", tags=["问候"])
    async def greeting_history(
        limit: int = Query(30, ge=1, le=200),
        db: AsyncSession = Depends(get_db),
    ):
        rows = (await db.execute(
            select(GreetingHistory).order_by(desc(GreetingHistory.id)).limit(limit)
        )).scalars().all()
        return [{
            "id": r.id, "type": r.type, "content": r.content,
            "trigger_time": r.trigger_time.isoformat() if r.trigger_time else None,
            "user_read": r.user_read,
        } for r in rows]

    # =========================================================
    # 6. 工具管理（贾维斯能力清单、开关、手动执行、日志）
    # =========================================================
    @app.get("/api/tools", tags=["工具"])
    async def list_tools():
        brain = get_brain()
        return brain.tools.list_all()

    class ToolToggle(BaseModel):
        name: str
        enabled: bool

    @app.post("/api/tools/toggle", tags=["工具"])
    async def toggle_tool(t: ToolToggle):
        brain = get_brain()
        try:
            brain.tools.set_enabled(t.name, t.enabled)
        except KeyError:
            raise HTTPException(404, "工具不存在")
        return {"ok": True, "name": t.name, "enabled": t.enabled}

    class ToolRunReq(BaseModel):
        name: str
        params: dict = Field(default_factory=dict)

    @app.post("/api/tools/run", tags=["工具"])
    async def run_tool(req: ToolRunReq, brain: Brain = Depends(get_brain)):
        meta_pair = brain.tools.get(req.name)
        if not meta_pair:
            raise HTTPException(404, "工具不存在")
        if not brain.tools.is_enabled(req.name):
            raise HTTPException(400, "工具已禁用")
        meta, func = meta_pair
        import asyncio as _aio
        import time as _t
        from .jarvis_tools import ToolResult
        t0 = _t.time()
        try:
            if _aio.iscoroutinefunction(func):
                r = await func(req.params)
            else:
                loop = _aio.get_running_loop()
                r = await loop.run_in_executor(None, func, req.params)
            if not isinstance(r, ToolResult):
                r = ToolResult(True, str(r), display=str(r))
            r.tool_name = req.name
            r.duration_ms = int((_t.time() - t0) * 1000)
        except Exception as e:
            r = ToolResult(False, str(e), display=f"❌ 执行失败：{e}", tool_name=req.name)
        # 写工具日志
        tl = ToolLog(
            tool_name=r.tool_name, user_text="[手动执行]",
            params_json=__import__("json").dumps(req.params, ensure_ascii=False),
            success=r.success, output=r.output[:6000],
            duration_ms=r.duration_ms,
        )
        try:
            sess = _SESSION_FACTORY()
            async with sess:
                sess.add(tl); await sess.commit()
        except Exception:
            pass
        return {
            "success": r.success,
            "output": r.output,
            "display": r.display,
            "duration_ms": r.duration_ms,
            "tool": r.tool_name,
        }

    @app.get("/api/tools/logs", tags=["工具"])
    async def tool_logs(
        tool: str = "", limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
    ):
        q = select(ToolLog).order_by(desc(ToolLog.id))
        if tool:
            q = q.where(ToolLog.tool_name == tool)
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [{
            "id": r.id, "tool": r.tool_name, "user_text": r.user_text,
            "success": r.success, "output_preview": (r.output or "")[:400],
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

    # =========================================================
    # 7. 提醒（倒计时 / 稍后提醒）
    # =========================================================
    @app.get("/api/reminders", tags=["提醒"])
    async def list_reminders(
        only_pending: bool = True,
        limit: int = Query(200, ge=1, le=1000),
        db: AsyncSession = Depends(get_db),
    ):
        q = select(Reminder).order_by(desc(Reminder.trigger_time))
        if only_pending:
            q = q.where(Reminder.triggered == False, Reminder.dismissed == False)
            q = q.order_by(Reminder.trigger_time.asc())
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [{
            "id": r.id, "note": r.note,
            "trigger_time": r.trigger_time.isoformat() if r.trigger_time else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "triggered": r.triggered, "dismissed": r.dismissed,
        } for r in rows]

    class ReminderAdd(BaseModel):
        note: str = Field(..., min_length=1, max_length=500)
        minutes: float = Field(..., gt=0, le=60*24*365)

    @app.post("/api/reminders", tags=["提醒"])
    async def add_reminder(ra: ReminderAdd, db: AsyncSession = Depends(get_db)):
        from datetime import timedelta
        trigger_at = datetime.now() + timedelta(minutes=float(ra.minutes))
        r = Reminder(note=ra.note, trigger_time=trigger_at)
        db.add(r); await db.commit(); await db.refresh(r)
        return {"ok": True, "id": r.id, "trigger_at": trigger_at.isoformat()}

    @app.post("/api/reminders/{rid}/dismiss", tags=["提醒"])
    async def dismiss_reminder(rid: int, db: AsyncSession = Depends(get_db)):
        r = await db.get(Reminder, rid)
        if not r: raise HTTPException(404)
        r.dismissed = True; await db.commit()
        return {"ok": True}

    @app.delete("/api/reminders/{rid}", tags=["提醒"])
    async def del_reminder(rid: int, db: AsyncSession = Depends(get_db)):
        r = await db.get(Reminder, rid)
        if not r: raise HTTPException(404)
        await db.delete(r); await db.commit()
        return {"ok": True}

    # =========================================================
    # 8. 贾维斯系统总览（给控制台页面）
    # =========================================================
    @app.get("/api/dashboard", tags=["系统"])
    async def dashboard(db: AsyncSession = Depends(get_db)):
        # 基础计数
        from sqlalchemy import func as f
        msg_n = (await db.execute(select(f.count(Message.id)))).scalar() or 0
        mem_n = (await db.execute(select(f.count(MemoryEntry.id)))).scalar() or 0
        rem_n = (await db.execute(
            select(f.count(Reminder.id)).where(Reminder.triggered == False, Reminder.dismissed == False)
        )).scalar() or 0
        tool_n = (await db.execute(select(f.count(ToolLog.id)))).scalar() or 0
        p = await Brain.get_persona(db)
        await db.commit()

        # 本机系统信息
        try:
            import os, shutil, platform
            sysinfo = {}
            sysinfo["platform"] = f"{platform.system()} {platform.release()} ({platform.machine()})"
            sysinfo["hostname"] = platform.node()
            sysinfo["python"] = platform.python_version()
            disk = shutil.disk_usage("/") if os.path.isdir("/") else None
            if disk:
                sysinfo["disk_total_gb"] = round(disk.total / 1024**3, 1)
                sysinfo["disk_used_gb"] = round(disk.used / 1024**3, 1)
                sysinfo["disk_usage_pct"] = round(disk.used / disk.total * 100, 1)
            if hasattr(os, "getloadavg"):
                sysinfo["loadavg"] = list(os.getloadavg())
            # 内存（Linux）
            mem_s = {}
            if platform.system() == "Linux" and os.path.isfile("/proc/meminfo"):
                with open("/proc/meminfo") as fp:
                    for l in fp.readlines()[:5]:
                        k, v = l.split(":")
                        mem_s[k.strip()] = int(v.strip().split()[0]) // 1024
                total = mem_s.get("MemTotal", 0)
                avail = mem_s.get("MemAvailable", mem_s.get("MemFree", 0))
                if total:
                    sysinfo["mem_total_mb"] = total
                    sysinfo["mem_used_mb"] = total - avail
                    sysinfo["mem_usage_pct"] = round((total - avail) / total * 100, 1)
            sysinfo["pid"] = os.getpid()
        except Exception as e:
            sysinfo = {"error": str(e)}

        return {
            "counts": {
                "messages": msg_n, "memories": mem_n,
                "pending_reminders": rem_n, "tool_runs": tool_n,
                "chats": p.total_chats,
            },
            "persona": {
                "name": p.name, "nickname": p.nickname_for_user,
                "trust": round(p.affection, 1), "stability": round(p.mood, 1),
                "mood_reason": p.mood_reason,
                "last_chat_at": p.last_chat_at.isoformat() if p.last_chat_at else None,
            },
            "system": sysinfo,
        }


# 注册路由
register_routes_app = register_routes   # alias; 下面实际注册
