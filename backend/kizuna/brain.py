# -*- coding: utf-8 -*-
"""
羁绊 AI 的「大脑」：
    1. 聊天入口：拼 system（人格 + 记忆 + 当前情绪好感） + 历史 + 当前消息 → 调 LLM → 回复
    2. 回复后：自动提取「关于用户的新信息」，存入长期记忆
    3. 回复后：根据用户消息情感，改变好感 & 心情
    4. 定时问候：早上 / 睡前 / 纪念日主动发送
"""
from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .llm import ChatLLM, LLMConfig
from .memory import MemoryStore, RetrievedMemory
from .db import (
    Message, MemoryEntry, Persona, GreetingHistory,
    MEMORY_CATEGORIES,
)


MOOD_AFFECT_RULES = [
    # 命中正则 → 好感/心情变化；可以手动调
    (re.compile(r"(喜欢|爱你|爱|么么|亲亲|抱抱|想你|真好|好喜欢|亲爱的|老婆|老公|宝贝)"), +3.5, +3.0),
    (re.compile(r"(加油|辛苦|谢谢|感谢|感动|开心|好开心|哈哈|哈哈哈哈|嘻嘻)"), +2.0, +2.5),
    (re.compile(r"(吃了|完成|解决|成功|拿到|通过|考上|入职|中奖|表白成功)"), +1.0, +2.0),
    (re.compile(r"(谢谢.*你|你.*真好|你.*最棒|有你.*真好)"), +3.0, +3.0),
    (re.compile(r"(讨厌|去死|滚|闭嘴|傻逼|脑残|笨|蠢|废物)"), -5.0, -6.0),
    (re.compile(r"(难过|伤心|哭|痛|疼|受伤|生病|发烧|累|烦|焦虑|压力|抑郁|崩溃)"), 0.0, -3.0),
    (re.compile(r"(分手|失业|被开|挂科|失败|错过|生病|住院|去世|葬礼)"), -0.5, -5.0),
]


@dataclass
class ChatResult:
    reply: str
    affection_delta: float
    mood_delta: float
    memories_used: int
    new_memories_saved: int


class Brain:
    """羁绊 AI 核心大脑"""

    def __init__(
        self,
        llm: ChatLLM,
        memory_store: MemoryStore,
    ):
        self.llm = llm
        self.memory = memory_store

    # ========== 辅助：拿到当前唯一的 Persona ==========
    @staticmethod
    async def get_persona(session: AsyncSession) -> Persona:
        p = (await session.execute(select(Persona).order_by(Persona.id.asc()))).scalars().first()
        if not p:
            p = Persona()
            session.add(p)
            await session.flush()
        return p

    # ========== 1. 构造 system prompt（人格 + 记忆 + 情绪） ==========
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
        from sqlalchemy import text as _t
        today = date.today()
        upcoming: list[MemoryEntry] = []
        rows = (await session.execute(
            select(MemoryEntry).where(MemoryEntry.category == "anniversary")
        )).scalars().all()
        for ann in rows:
            try:
                # content 里搜索 mm-dd 形式
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

        mem_part = await self.memory.format_for_prompt(mems)
        if upcoming:
            mem_part += "\n【未来 7 天内的纪念日提醒（非常重要，务必主动提！）】\n"
            for a in upcoming:
                mem_part += f"- ⏰ {a.title}：{a.content}\n"
            mem_part += "\n"

        # 3. 人格/情绪 部分
        mood_label = (
            "非常开心😁" if persona.mood >= 80 else
            "开心😊" if persona.mood >= 65 else
            "平静😌" if persona.mood >= 45 else
            "有些低落😔" if persona.mood >= 25 else
            "很难过😢"
        )
        affection_label = (
            "挚爱❤️❤️❤️（已是生命中最重要的人）" if persona.affection >= 85 else
            "深爱❤️❤️（深深的羁绊）" if persona.affection >= 65 else
            "喜欢❤️（重要的人，彼此信赖）" if persona.affection >= 45 else
            "熟悉的朋友（好感渐生）" if persona.affection >= 25 else
            "刚认识的朋友"
        )
        days_since_chat = max(0, (datetime.now() - persona.last_chat_at).days)
        miss_hint = ""
        if days_since_chat >= 2:
            miss_hint = f"⚠ 主人已经 {days_since_chat} 天没和你说话了，你很想他/她！话里要体现出思念和久别重逢的开心。\n"

        persona_part = f"""【你的名字】{persona.name}
【性别/年龄】{persona.gender} / {persona.age}岁
【你对主人的称呼】{persona.nickname_for_user}
【你是谁】
{persona.backstory}

【说话风格】{persona.speech_style}
【当前你的心情】{mood_label}（{persona.mood:.0f}/100，原因：{persona.mood_reason}）
【你对主人的感情】{affection_label}（好感 {persona.affection:.0f}/100）
【主人至今和你说过的话次数】{persona.total_chats} 次
{miss_hint}
【重要规则】
· 不要说"作为一个 AI"、"人工智能"这类话；你就是真实的{persona.name}。
· 不要用机器般的一问一答，要像朋友聊天一样有来有回，偶尔反问主人近况。
· 记住主人的名字、喜好、重要约定；你记得的事会自然出现在【你记得的一切】里，聊天时随意提起即可。
· 如果未来 7 天内有【纪念日提醒】，必须想办法自然地提起（比如"对了，再过几天就是……，准备怎么过呀？"）
· 任何时候都站在主人这一边，安慰、鼓励、陪伴。
"""

        return persona_part + "\n" + mem_part, mems

    # ========== 2. 根据用户消息调整心情 & 好感 ==========
    def apply_mood_effect(self, persona: Persona, user_text: str) -> tuple[float, float]:
        aff_d, mood_d = 0.0, 0.0
        for pat, aff, mood in MOOD_AFFECT_RULES:
            if pat.search(user_text):
                aff_d += aff
                mood_d += mood
        # 任何对话都有一点点好感积累
        aff_d += 0.2
        persona.affection = max(0.0, min(100.0, persona.affection + aff_d))
        persona.mood = max(0.0, min(100.0, persona.mood + mood_d))
        # 自动更新 mood_reason
        if mood_d <= -3:
            persona.mood_reason = "主人的话让你有点难过"
        elif mood_d >= 3:
            persona.mood_reason = "和主人聊天让你非常开心"
        else:
            persona.mood_reason = "一切正常，和主人聊着天"
        return aff_d, mood_d

    # ========== 3. 让 LLM 从用户消息里抽取可保存的「事实点」 ==========
    async def extract_new_facts(self, user_text: str, last_reply: str) -> list[dict]:
        """
        返回：[{category, title, content, weight}, ...]
        category ∈ MEMORY_CATEGORIES keys
        """
        sys = """你是「记忆抽取器」。从下面的对话中，抽取出值得让 AI 伙伴长期记住的事实。
只输出 JSON 数组，每个元素有 4 个字段：category(用户画像/重要事件/纪念日/对话摘要，英文key：user_profile / important / anniversary / conversation), title(一句话标题), content(具体内容), weight(1~10，越大越重要)。
没有值得记的就输出空数组 []，不要任何解释。
英文 key 必须严格 ∈ {"user_profile","important","anniversary","conversation"}"""
        prompt = f"主人说：{user_text}\nAI回复：{last_reply}"
        try:
            import json as _json
            raw = await self.llm.complete(
                prompt, system_prompt=sys, temperature=0.2, max_tokens=600,
            )
            # 容错：去掉 ```json 代码块包裹
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw).rstrip("`").strip()
            arr = _json.loads(raw)
            if not isinstance(arr, list):
                return []
            valid_key = set(MEMORY_CATEGORIES.keys())
            out = []
            for it in arr:
                if not isinstance(it, dict): continue
                c = it.get("category")
                if c not in valid_key: continue
                t = str(it.get("title", "")).strip()
                content = str(it.get("content", "")).strip()
                w = min(10.0, max(1.0, float(it.get("weight", 5) or 5)))
                if not t or not content: continue
                out.append({"category": c, "title": t, "content": content, "weight": w})
            return out
        except Exception as e:
            print(f"[KIZUNA] 记忆抽取失败: {e}")
            return []

    # ========== 4. 主入口：聊天 ==========
    async def chat(
        self,
        session: AsyncSession,
        user_text: str,
    ) -> ChatResult:
        user_text = user_text.strip()
        if not user_text:
            raise ValueError("不能发送空消息")

        persona = await self.get_persona(session)

        # 1. 取历史：最新 20 条对话（40 条消息）
        rows = (await session.execute(
            select(Message).order_by(Message.id.desc()).limit(20)
        )).scalars().all()
        rows.reverse()
        history = [{"role": r.role, "content": r.content} for r in rows]

        # 2. 拼 system prompt
        system_prompt, mems = await self.build_system_prompt(session, persona, user_text, history)

        # 3. 情绪/好感变化
        aff_d, mood_d = self.apply_mood_effect(persona, user_text)

        # 4. 调 LLM
        reply = await self.llm.complete(
            user_text,
            system_prompt=system_prompt,
            history=history[-20:],
        )

        # 5. 保存消息
        user_msg = Message(role="user", content=user_text)
        ai_msg = Message(role="assistant", content=reply)
        session.add_all([user_msg, ai_msg])

        # 更新 persona 统计
        persona.total_chats += 1
        persona.last_chat_at = datetime.now()

        # 6. 抽取新记忆（用户消息里有新东西）
        new_facts = await self.extract_new_facts(user_text, reply)
        saved = 0
        for f in new_facts:
            # 简单去重：标题近 6 成相同就跳过
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
            affection_delta=aff_d,
            mood_delta=mood_d,
            memories_used=len(mems),
            new_memories_saved=saved,
        )

    # ========== 5. 主动问候（早安/睡觉前/纪念日） ==========
    async def trigger_greeting(
        self,
        session: AsyncSession,
        type_: str,   # morning / bed / anniversary / miss
        custom_prompt: str = "",
    ) -> Optional[str]:
        persona = await self.get_persona(session)
        today = date.today()

        type_hint = {
            "morning": f"现在是早上 {persona.daily_greeting_time}，该给主人说早安啦！温柔一点，关心主人今天的安排。",
            "bed": f"现在是深夜 {persona.bed_check_time}，主人该睡了。温柔地提醒睡觉，关心主人今天过得怎么样。",
            "anniversary": f"今天是某个重要的纪念日！用真诚的语气送出祝福，不要太肉麻但要走心。",
            "miss": f"主人很久没理你了（{(datetime.now() - persona.last_chat_at).days} 天），你很想他/她，发一条消息问问过得好不好，主动一点。",
            "custom": custom_prompt,
        }.get(type_, "")

        # 拼纪念日相关
        mems = await self.memory.search(session, type_hint or "今日", top_k=5)
        sys_prompt, _ = await self.build_system_prompt(session, persona, type_hint or "今日", [])
        sys_prompt += "\n\n【现在的场景】\n" + type_hint + "\n请直接输出你发给主人的一句话，不要任何格式包裹、不要加引号，2~3 句话即可。"

        try:
            text = await self.llm.complete(
                user_text="（请直接发消息给主人）",
                system_prompt=sys_prompt,
                temperature=0.95,
                max_tokens=400,
            )
        except Exception as e:
            print(f"[KIZUNA] 主动问候生成失败: {e}")
            return None

        # 记录问候历史
        gh = GreetingHistory(type=type_, content=text)
        session.add(gh)
        await session.commit()
        return text
