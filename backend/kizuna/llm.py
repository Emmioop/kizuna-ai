# -*- coding: utf-8 -*-
"""
多模型适配层
    统一对接各家大模型：OpenAI 兼容协议 / 智谱 / DeepSeek / 阿里通义 / 月之暗面 / 本地 Oobabooga
所有类实现：async complete(prompt, system_prompt=, temperature=, max_tokens=) -> str
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field


# ==================== 配置 ====================
SUPPORTED_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "zhipu": {
        "name": "智谱 AI (GLM)",
        "base": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "name": "通义千问",
        "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "moonshot": {
        "name": "月之暗面 Kimi",
        "base": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "ollama": {
        "name": "Ollama 本地模型",
        "base": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
    },
    "custom": {
        "name": "自定义兼容接口",
        "base": "",
        "default_model": "",
    },
}


class LLMConfig(BaseModel):
    provider: str = Field(default="zhipu", description="供应商 key，见 SUPPORTED_PROVIDERS")
    api_key: str = Field(default="", description="API Key")
    base_url: Optional[str] = Field(default=None, description="自定义 base_url，覆盖供应商默认")
    model: Optional[str] = Field(default=None, description="模型名称，覆盖供应商默认")
    temperature: float = Field(default=0.75, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1200, ge=1)
    timeout: int = Field(default=60)


# ==================== 实现 ====================
class ChatLLM:
    """通用 OpenAI 兼容客户端"""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.provider_meta = SUPPORTED_PROVIDERS.get(cfg.provider, SUPPORTED_PROVIDERS["custom"])

        # base & model 计算优先级：传入 > env > provider 默认
        self.base = (
            cfg.base_url
            or os.environ.get("KIZUNA_LLM_BASE")
            or self.provider_meta["base"]
        )
        self.model = (
            cfg.model
            or os.environ.get("KIZUNA_LLM_MODEL")
            or self.provider_meta["default_model"]
        )
        self.api_key = (
            cfg.api_key
            or os.environ.get("KIZUNA_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )

        if not self.base:
            raise ValueError("供应商为 custom 时必须提供 base_url 或设置 KIZUNA_LLM_BASE")

    @property
    def provider_label(self) -> str:
        return self.provider_meta["name"]

    # ---------- 核心：发送请求 ----------
    async def complete(
        self,
        user_text: str,
        *,
        system_prompt: str = "你是一个温暖、忠诚、善解人意的 AI 伙伴。",
        history: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """给一段用户文本 + 系统提示 + 历史，返回一句话回复"""
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Ollama 允许空 key，但 deepseek/zhipu 不行
        if not self.api_key:
            headers.pop("Authorization", None)

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.cfg.temperature,
            "max_tokens": max_tokens or self.cfg.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
            resp = await client.post(
                self.base.rstrip("/") + "/chat/completions",
                headers=headers,
                json=body,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"[{self.provider_label}] 请求失败({resp.status_code}): {resp.text[:200]}"
                )
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"[{self.provider_label}] 返回格式异常: {data}") from e

    async def stream(
        self,
        user_text: str,
        *,
        system_prompt: str = "你是一个温暖、忠诚、善解人意的 AI 伙伴。",
        history: list[dict] | None = None,
        temperature: float | None = None,
    ):
        """生成器版本：流式返回（可省，SSE）"""
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if not self.api_key:
            headers.pop("Authorization", None)

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
            async with client.stream(
                "POST",
                self.base.rstrip("/") + "/chat/completions",
                headers=headers,
                json=body,
            ) as r:
                if r.status_code != 200:
                    t = await r.aread()
                    raise RuntimeError(f"[{self.provider_label}] 流式失败({r.status_code}): {t[:200]}")
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        return
                    try:
                        import json as _json
                        chunk = _json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue
