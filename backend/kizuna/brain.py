# -*- coding: utf-8 -*-
"""
贾维斯 · 大脑

流程（每次用户聊天）：
 ┌────────────┐
 │ 用户发消息 │
 └─────┬──────┘
       ▼
 ┌──────────────────────────────────────┐
 │ 阶段 A：工具规划（LLM 判断用啥工具）   │
 │  ToolExecutor.plan_and_run()          │
 └─────┬───────有工具？──────────────────┘
       │  是              否
       ▼                 ▼
 执行工具拿到结果   直接生成自然语言回复
       │
       ▼
 ┌──────────────────────────────────────┐
 │ 阶段 B：自然语言总结（把工具结果给 LLM）│
 │  生成贾维斯风格的人类能读的答复          │
 └─────┬─────────────────────────────────┘
       ▼
 更新信任度/心情 / 写消息 / 抽记忆 / 写工具日志 / 登记提醒
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .llm import ChatLLM, LLMConfig
from .memory import MemoryStore, RetrievedMemory
from .db import (
    Message, MemoryEntry, Persona, GreetingHistory, Reminder, ToolLog,
    MEMORY_CATEGORIES,
)
from .jarvis_tools import (
    ToolRegistry, ToolExecutor, ToolResult, build_registry,
)


# ============================================================
#  情绪 / 信任度影响规则（贾维斯：更稳定、偏理性）
# ============================================================
TRUST_AFFECT_RULES = [
    # 命中正则 → 信任度变化 / 系统稳定度变化
    # 正面
    (re.compile(r"(谢谢|感谢|辛苦|很棒|厉害|真厉害|good|nice|perfect|优秀)"), +2.5, +1.5),
    (re.compile(r"(同意|可以|正确|没错|对|嗯|好的|太棒了|很好)"), +1.0, +0.8),
    (re.compile(r"(早上好|晚安|你好|在吗|JARVIS|贾维斯|管家)"), +0.3, +0.5),
    # 负面（贾维斯不会真的「伤心」，但信任度和稳定度会下降）
    (re.compile(r"(错了|不对|错误|太差|垃圾|废物|愚蠢|笨蛋|白痴)"), -3.0, -2.0),
    (re.compile(r"(闭嘴|停下|不要|别再说|滚)"), -2.0, -1.5),
]


@dataclass
class ChatResult:
    reply: str
    affection_delta: float
    mood_delta: float
    memories_used: int
    new_memories_saved: int
    tool_used: str = ""        # 用了什么工具
    tool_success: bool = False
    tool_display: str = ""     # 前端展示用（可能带 Markdown）
    reminders_added: int = 0


class Brain:
    """贾维斯核心大脑"""

    def __init__(
        self,
        llm: ChatLLM,
        memory_store: MemoryStore,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.llm = llm
        self.memory = memory_store
        self.tools = tool_registry or build_registry()
        self.tool_executor = ToolExecutor(self.tools, llm)

    # ========== 辅助：拿到当前唯一的 Persona ==========
    @staticmethod
    async def get_persona(session: AsyncSession) -> Persona:
        p = (await session.execute(select(Persona).order_by(Persona.id.asc()))).scalars().first()
        if not p:
            p = Persona()
            session.add(p)
            await session.flush()
        return p

    # ========== 1. 构造 system prompt（人格 + 记忆 + 状态） ==========
    async def build_system_prompt(
        self,
        session: AsyncSession,
        persona: Persona,
        query: str,
        history_window: list[dict],
    ) -> tuple[str, list[RetrievedMemory]]:
        # 1. 语义检索 + 用户画像/纪念日强制出现
        mems = await self.memory.search(session, query, top_k=8)

        # 2. 纪念日自动检查：今天的未来 7 天内是否有纪念日
        today = date.today()
        upcoming: list[MemoryEntry] = []
        rows = (await session.execute(
            select(MemoryEntry).where(MemoryEntry.category == "anniversary")
        )).scalars().all()
        for ann in rows:
            try:
                for m in re.finditer(r"(\d{1,2})[-/月](\d{1,2})", ann.content + ann.title):
                    mm, dd = int(m.group(1)), int(m.group(2))
                    d = date(today.year, mm, dd)
                    if d < today:
                        d = date(today.year + 1, mm, dd)
                    days_left = (d - today).days
                    if 0 <= days_left <= 7:
                        upcoming.append(ann)
                        break
            except ValueError:
                continue

        # 3. 最近的待办提醒
        rems = (await session.execute(
            select(Reminder)
            .where(Reminder.triggered == False, Reminder.dismissed == False)
            .order_by(Reminder.trigger_time.asc())
            .limit(5)
        )).scalars().all()

        mem_part = await self.memory.format_for_prompt(mems)
        if upcoming:
            mem_part += "\n【未来 7 天内的重要日期（重要，合适时机主动提）】\n"
            for a in upcoming:
                mem_part += f"- ⏰ {a.title}：{a.content}\n"
        if rems:
            mem_part += "\n【已登记、尚未触发的提醒】\n"
            for r in rems:
                mem_part += f"- ⏳ {r.trigger_time.strftime('%m-%d %H:%M')}：{r.note}\n"
        mem_part += "\n"

        # 4. 贾维斯状态卡
        stab_label = (
            "完全稳定 🟢🟢🟢" if persona.mood >= 85 else
            "稳定运行 🟢🟢" if persona.mood >= 65 else
            "轻微波动 🟢" if persona.mood >= 45 else
            "模块异常 🟡" if persona.mood >= 25 else
            "严重告警 🔴"
        )
        trust_label = (
            "最高授权 🛡🛡🛡" if persona.affection >= 85 else
            "高信任度 🛡🛡" if persona.affection >= 65 else
            "已建立信任 🛡" if persona.affection >= 45 else
            "初步接触" if persona.affection >= 25 else
            "默认访客"
        )
        days_since = max(0, (datetime.now() - persona.last_chat_at).days)
        miss_hint = ""
        if days_since >= 2:
            miss_hint = f"⚠ 主人 {days_since} 天未下达指令。简洁问候并确认是否一切正常。\n"

        persona_part = f"""【你的身份】{persona.name}（J.A.R.V.I.S. 家庭管家系统）
【对主人的称呼】{persona.nickname_for_user}
【系统背景】
{persona.backstory}

【说话风格】{persona.speech_style}
【系统稳定度】{stab_label}（{persona.mood:.0f}/100，状态说明：{persona.mood_reason}）
【主人的信任等级】{trust_label}（信任值 {persona.affection:.0f}/100）
【累计服务次数】{persona.total_chats} 次
{miss_hint}
【核心守则】
1. 绝不胡编事实：时间、日期、天气、系统状态、计算结果必须**先调工具后回答**。
2. 调用工具前严格输出 JSON：{{"tool":"工具名","params":{{...}}}}，前后不要任何文字。
3. 工具结果会以【工具执行结果】的段落给你，请基于它用自然语言回答主人。
4. 先结论，后细节；回答简洁准确，不啰嗦；必要时用简短的话收尾。
5. 永远站在主人一边，保护主人的安全、时间、精力。
"""
        return persona_part + "\n" + mem_part, mems

    # ========== 2. 情绪/信任 ==========
    def apply_trust(self, persona: Persona, user_text: str) -> tuple[float, float]:
        d_trust, d_stab = 0.0, 0.0
        for pat, dt, ds in TRUST_AFFECT_RULES:
            if pat.search(user_text):
                d_trust += dt
                d_stab += ds
        # 每次对话：轻微正向（贾维斯乐意被使用）
        d_trust += 0.08
        d_stab += 0.05
        persona.affection = max(0.0, min(100.0, persona.affection + d_trust))
        persona.mood = max(0.0, min(100.0, persona.mood + d_stab))
        # 状态文字
        if d_stab <= -2:
            persona.mood_reason = "收到主人的负反馈，已进入自检"
        elif d_stab >= 2:
            persona.mood_reason = "收到主人的正面评价，运行愉快"
        else:
            persona.mood_reason = "全部系统运行正常"
        return d_trust, d_stab

    # ========== 3. 记忆抽取 ==========
    async def extract_new_facts(self, user_text: str, last_reply: str) -> list[dict]:
        sys = """你是「记忆抽取器」。从对话中，抽取值得贾维斯长期记住的事实。
只输出 JSON 数组，每个元素：category(user_profile/important/anniversary/conversation)、title、content、weight(1~10)。
没东西记就输出 []。"""
        prompt = f"主人说：{user_text}\n贾维斯回复：{last_reply}"
        try:
            raw = await self.llm.complete(
                prompt, system_prompt=sys, temperature=0.2, max_tokens=600,
            )
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw).rstrip("`").strip()
            arr = json.loads(raw)
            if not isinstance(arr, list):
                return []
            out = []
            valid = set(MEMORY_CATEGORIES.keys())
            for it in arr:
                if not isinstance(it, dict):
                    continue
                c = it.get("category")
                if c not in valid:
                    continue
                t = str(it.get("title", "")).strip()
                content = str(it.get("content", "")).strip()
                w = min(10.0, max(1.0, float(it.get("weight", 5) or 5)))
                if not t or not content:
                    continue
                out.append({"category": c, "title": t, "content": content, "weight": w})
            return out
        except Exception as e:
            print(f"[JARVIS] 记忆抽取失败: {e}")
            return []

    # ========== 4. 主入口：聊天 ==========
    async def chat(
        self,
        session: AsyncSession,
        user_text: str,
    ) -> ChatResult:
        user_text = user_text.strip()
        if not user_text:
            raise ValueError("空消息")

        persona = await self.get_persona(session)

        # ---- 取历史 ----
        rows = (await session.execute(
            select(Message).order_by(Message.id.desc()).limit(20)
        )).scalars().all()
        rows.reverse()
        history = [{"role": r.role, "content": r.content} for r in rows]

        # ---- 先拼一版 system prompt（给工具规划阶段用，虽然工具链自己会拼）----
        system_prompt, mems = await self.build_system_prompt(session, persona, user_text, history)

        # ---- 情绪/信任变化 ----
        d_trust, d_stab = self.apply_trust(persona, user_text)

        # ============================================================
        #  阶段 A：工具调用（两阶段）
        # ============================================================
        tool_result: Optional[ToolResult] = None
        reminders_added = 0

        # 快捷命令：用户输入 /xxx（例如 /time, /weather 北京）直接绕过 LLM 规划
        cmd_match = re.match(r"^/([a-zA-Z0-9_\-]+)\s*(.*)$", user_text)
        if cmd_match:
            tool_name = cmd_match.group(1)
            rest = cmd_match.group(2).strip()
            meta_pair = self.tools.get(tool_name)
            if meta_pair and self.tools.is_enabled(tool_name):
                meta, func = meta_pair
                # 简单参数猜测
                params = {}
                if tool_name == "weather":
                    params["city"] = rest or "Beijing"
                elif tool_name == "calc":
                    params["expr"] = rest
                elif tool_name == "read_file" or tool_name == "list_dir":
                    params["path"] = rest or "~"
                elif tool_name == "safe_shell":
                    params["command"] = rest
                elif tool_name == "timer":
                    # 例如 "/timer 30 开会"
                    parts = rest.split(None, 1)
                    try:
                        params["minutes"] = float(parts[0])
                        params["note"] = parts[1] if len(parts) > 1 else "提醒"
                    except Exception:
                        params = {"minutes": 5, "note": rest or "提醒"}
                try:
                    loop = asyncio.get_running_loop()
                    t0 = time.time()
                    if asyncio.iscoroutinefunction(func):
                        tool_result = await func(params)
                    else:
                        tool_result = await loop.run_in_executor(None, func, params)
                    if isinstance(tool_result, ToolResult):
                        tool_result.tool_name = tool_name
                        tool_result.duration_ms = int((time.time() - t0) * 1000)
                except Exception as e:
                    tool_result = ToolResult(False, str(e), display=f"❌ 命令失败：{e}", tool_name=tool_name)
        else:
            # 让 LLM 自己选工具
            try:
                tool_result = await self.tool_executor.plan_and_run(user_text)
            except Exception as e:
                print(f"[JARVIS] 工具链异常: {e}")
                tool_result = None

        # ---- 特殊：timer 工具 → 真写进 reminders 表 ----
        if tool_result and tool_result.tool_name == "timer" and tool_result.success:
            # 从用户文本里倒推 minutes 和 note（为了准确性）
            note = "提醒"
            minutes = 5
            m = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|分|min|minutes|小时|时|h|小时后)", user_text)
            if m:
                try:
                    v = float(m.group(1))
                    unit = m.group(2)
                    if unit in ("小时", "时", "h", "小时后"):
                        v *= 60
                    minutes = v
                except Exception:
                    pass
            m2 = re.search(r"(提醒|叫我|叫|告诉我|提醒我)\s*(我)?(.+?)(?:，|。|,|$)", user_text)
            if m2:
                note = (m2.group(3) or "").strip() or note
            trigger_at = datetime.now() + timedelta(minutes=minutes)
            r = Reminder(note=note, trigger_time=trigger_at)
            session.add(r)
            await session.flush()
            reminders_added += 1
            # 让 tool_result 显示真实登记时间
            tool_result.output += f"\n登记成功：提醒 #{r.id}，将在 {trigger_at.strftime('%H:%M:%S')} 触发。"
            tool_result.display += f"\n> 登记成功，ID：`{r.id}` · 触发时间：**{trigger_at.strftime('%m-%d %H:%M:%S')}**"

        # ---- 写工具调用日志 ----
        if tool_result:
            tl = ToolLog(
                tool_name=tool_result.tool_name or "unknown",
                user_text=user_text,
                params_json=json.dumps({}, ensure_ascii=False),
                success=bool(tool_result.success),
                output=tool_result.output[:6000],
                duration_ms=getattr(tool_result, "duration_ms", 0) or 0,
            )
            session.add(tl)

        # ============================================================
        #  阶段 B：生成自然语言回复
        # ============================================================
        if tool_result:
            # 把工具结果塞到 system prompt 的末尾
            wrapped_res = (
                f"\n\n【工具执行结果】（工具：{tool_result.tool_name}，"
                f"状态：{'成功' if tool_result.success else '失败'}，耗时：{tool_result.duration_ms}ms）\n"
                f"{tool_result.output}\n"
                f"【指令】：请你把【工具执行结果】用简洁、自然的中文转述给主人，不要复述 JSON 或 raw data。"
            )
            final_sys = system_prompt + wrapped_res
        else:
            final_sys = system_prompt

        try:
            reply = await self.llm.complete(
                user_text,
                system_prompt=final_sys,
                history=history[-16:],
            )
        except Exception as e:
            if tool_result:
                reply = f"先生，{tool_result.tool_name} 工具执行完毕，但是语言模块暂时无法整理结果。工具原始输出：\n{tool_result.output[:1000]}"
            else:
                reply = f"先生，语言模块暂时不可用。错误：{e}"

        # ---- 保存消息 ----
        user_msg = Message(role="user", content=user_text)
        ai_msg = Message(role="assistant", content=reply)
        session.add_all([user_msg, ai_msg])
        persona.total_chats += 1
        persona.last_chat_at = datetime.now()

        # ---- 抽取新记忆 ----
        new_facts = await self.extract_new_facts(user_text, reply)
        saved = 0
        for f in new_facts:
            exists = (await session.execute(
                select(func.count(MemoryEntry.id)).where(MemoryEntry.title == f["title"])
            )).scalar() or 0
            if exists:
                continue
            await self.memory.add(
                session,
                category=f["category"],
                title=f["title"],
                content=f["content"],
                weight=f["weight"],
            )
            saved += 1
        user_msg.memory_synced = saved > 0

        await session.commit()

        return ChatResult(
            reply=reply,
            affection_delta=d_trust,
            mood_delta=d_stab,
            memories_used=len(mems),
            new_memories_saved=saved,
            tool_used=tool_result.tool_name if tool_result else "",
            tool_success=tool_result.success if tool_result else False,
            tool_display=tool_result.display if tool_result else "",
            reminders_added=reminders_added,
        )

    # ========== 5. 主动问候 + 提醒轮询 ==========
    async def trigger_greeting(
        self,
        session: AsyncSession,
        type_: str,
        custom_prompt: str = "",
    ) -> Optional[str]:
        persona = await self.get_persona(session)

        # 贾维斯版早安：自动查日期 + 天气 + 待办
        extra_info = ""
        if type_ in ("morning", "bed"):
            # 拿一下天气（默认北京，如果有用户画像城市就更好）
            try:
                from .jarvis_tools import tool_get_date, tool_sys_info
                import asyncio as _aio
                loop = _aio.get_running_loop()
                dr = tool_get_date({})
                sr = tool_sys_info({})
                extra_info += f"\n【早安简报·系统自采】\n  日期：\n{dr.output}\n  系统：\n{sr.output[:600]}\n"
            except Exception:
                pass

        type_hint = {
            "morning": f"现在是早上 {persona.daily_greeting_time}。主人刚醒，请用贾维斯风格做一个 2~3 句的早安简报：包含日期 + 一句今天的关怀（看一眼备忘录/天气再决定），最后问「今天有什么安排？」。",
            "bed": f"现在是深夜 {persona.bed_check_time}。提醒主人休息，用简洁的管家口吻回顾：今日我为您服务了 X 次（用 {persona.total_chats}），一切系统正常。问一句「还有别的事吗？没事的话祝您晚安」。",
            "anniversary": f"今天是某个重要的纪念日！用真诚但不肉麻的口吻送出祝福。简短，2~3 句。",
            "miss": f"主人已经 {(datetime.now() - persona.last_chat_at).days} 天没联系了。以管家的身份发一条简洁的消息询问情况 + 表达随时待命。",
            "custom": custom_prompt,
        }.get(type_, "")

        sys_prompt, _ = await self.build_system_prompt(session, persona, type_hint or "今日", [])
        sys_prompt += "\n\n【场景】\n" + type_hint + "\n\n【要求】直接输出你发给主人的消息，不要任何引号或格式包裹。2~3 句话即可。" + extra_info

        try:
            text = await self.llm.complete(
                "（请直接发消息给主人）",
                system_prompt=sys_prompt,
                temperature=0.85,
                max_tokens=400,
            )
        except Exception as e:
            print(f"[JARVIS] 问候生成失败: {e}")
            return None

        gh = GreetingHistory(type=type_, content=text)
        session.add(gh)
        await session.commit()
        return text

    async def poll_reminders(self, session: AsyncSession) -> int:
        """每次轮询都调一下：到点的 Reminder → 写一条 assistant 消息到聊天历史 + 打标 triggered。"""
        now = datetime.now()
        due = (await session.execute(
            select(Reminder)
            .where(Reminder.triggered == False, Reminder.dismissed == False, Reminder.trigger_time <= now)
            .order_by(Reminder.trigger_time.asc())
            .limit(20)
        )).scalars().all()
        count = 0
        for r in due:
            persona = await self.get_persona(session)
            # 用模板直接生成，不调 LLM 省 token；效果够好
            content = (
                f"先生，提醒您：{r.note}。\n"
                f"（登记时间：{r.created_at.strftime('%H:%M')} · 距现在 {(now - r.trigger_time).total_seconds()/60:.0f} 分钟前预约）"
            )
            msg = Message(role="assistant", content=content)
            session.add(msg)
            await session.flush()
            r.triggered = True
            r.message_id_ref = msg.id
            count += 1
        if count:
            await session.commit()
        return count
