# -*- coding: utf-8 -*-
"""
贾维斯 · 工具调用框架（Just A Rather Very Intelligent System）

思路：
  1. 每个工具 = 一个 @tool 装饰的函数，包含元数据（name/description/参数 schema/example）
  2. ToolRegistry 管理所有工具（启用/禁用、权限白名单）
  3. ToolExecutor 给一段用户文本 → 让 LLM 选工具 + 解析参数 → 执行 → 返回结构化结果
  4. 结果再塞回 LLM，让它用自然语言总结给用户（两阶段调用）

为什么不用 OpenAI 原生 Function Calling？
  因为要兼容 7 家供应商，原生支持参差不齐。用纯 LLM + JSON 解析更通用，
  效果其实几乎一样（只要 system prompt 写清楚）。
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import platform
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Callable, Optional

import httpx


# ============================================================
#  安全：白名单 shell 命令（防止用户让贾维斯 rm -rf /）
# ============================================================
SAFE_SHELL_WHITELIST = {
    # 系统信息
    "date": "date",
    "uptime": "uptime",
    "whoami": "whoami",
    "uname -a": "uname -a",
    # 磁盘
    "df -h": "df -h",
    "du -sh *": None,  # 需路径参数，单独处理
    # 进程/资源
    "ps aux | head -20": None,
    "free -h": "free -h",
    "top -bn1 | head -20": None,
    # 网络
    "ping -c 2 127.0.0.1": None,
    "curl -s ifconfig.me": None,
}

# 允许读的目录（防止读 /etc/passwd 之类）
ALLOWED_READ_PREFIXES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    os.path.expanduser("~"),
]


# ============================================================
#  工具元数据
# ============================================================
@dataclass
class ToolMeta:
    name: str
    description: str          # 给 LLM 看的说明
    params_schema: dict       # JSON Schema 风格：{key: {"type": "string", "desc": "...", "required": bool}}
    examples: list[str] = field(default_factory=list)
    category: str = "general" # general / system / info / reminder
    enabled_default: bool = True
    dangerous: bool = False   # 是否需要额外权限（比如写文件）


@dataclass
class ToolResult:
    success: bool
    output: str          # 给 LLM 二次总结用的纯文本
    display: str = ""    # 给前端 UI 展示的（可包含 Markdown）
    tool_name: str = ""
    duration_ms: int = 0


class ToolError(Exception):
    pass


# ============================================================
#  工具注册表
# ============================================================
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[ToolMeta, Callable]] = {}
        self._disabled: set[str] = set()

    def register(self, meta: ToolMeta, func: Callable):
        self._tools[meta.name] = (meta, func)

    def get(self, name: str) -> Optional[tuple[ToolMeta, Callable]]:
        return self._tools.get(name)

    def list_all(self) -> list[dict]:
        out = []
        for name, (meta, _) in self._tools.items():
            out.append({
                "name": name,
                "description": meta.description,
                "category": meta.category,
                "params_schema": meta.params_schema,
                "examples": meta.examples,
                "enabled": name not in self._disabled,
                "dangerous": meta.dangerous,
            })
        return out

    def set_enabled(self, name: str, enabled: bool):
        if name not in self._tools:
            raise KeyError(name)
        if enabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)

    def is_enabled(self, name: str) -> bool:
        return name in self._tools and name not in self._disabled

    # ---- 给 LLM 看的工具清单（自动生成，塞到 system prompt）----
    def format_for_llm(self) -> str:
        lines = ["【你可以调用的内部工具（非常重要！）】"]
        lines.append("先判断用户的需求能不能用工具解决。能用就**先调用工具**，拿到结果再回答；不能用就直接回答。")
        lines.append("调用工具时严格只输出一个 JSON 对象（前后不要任何文字），格式：")
        lines.append('  {"tool": "工具名", "params": {"参数1": "值1"}}')
        lines.append("下面是全部可用工具及参数：\n")
        for name, (meta, _) in self._tools.items():
            if not self.is_enabled(name):
                continue
            params_desc = []
            for pname, pschema in meta.params_schema.items():
                req = "必填" if pschema.get("required") else "可选"
                params_desc.append(f"    - {pname} ({req})：{pschema.get('desc', '')}")
            lines.append(f"• 工具名：{name}【{meta.category}】")
            lines.append(f"  说明：{meta.description}")
            if params_desc:
                lines.append("  参数：")
                lines.extend(params_desc)
            if meta.examples:
                lines.append("  例子：")
                for ex in meta.examples:
                    lines.append(f"    需求：{ex}")
        lines.append("\n【重要规则】")
        lines.append("1. 需要时间/日期/天气/系统状态/磁盘/计算 → 必须用工具，别自己猜（你没有实时时钟）")
        lines.append("2. 工具结果会作为【工具执行结果】给你，再用自然语言总结给用户")
        lines.append("3. 你**只能输出一次 JSON 工具调用**，我会执行并把结果返回来，你再用文字回答用户")
        lines.append("4. 如果不确定用什么工具或参数，直接输出 {\"tool\":\"\",\"params\":{}} 表示不调用\n")
        return "\n".join(lines)


# ============================================================
#  具体工具实现
# ============================================================
# ---------- 1. 时间 / 日期 ----------
def tool_get_time(params: dict) -> ToolResult:
    now = datetime.now()
    out = f"当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S %A')}\n"
    out += f"ISO：{now.isoformat()}\n"
    out += f"Unix 时间戳：{int(now.timestamp())}\n"
    tz = os.environ.get("TZ", "未设置")
    out += f"时区：{tz}\n"
    return ToolResult(True, out, display=now.strftime("🕐 **%Y-%m-%d %H:%M:%S** · %A"))


def tool_get_date(params: dict) -> ToolResult:
    today = date.today()
    out = f"今天日期：{today.isoformat()}（{today.strftime('%A')}）\n"
    out += f"今年第 {today.timetuple().tm_yday} 天 / 第 {today.isocalendar()[1]} 周\n"
    next7 = [(today + timedelta(days=i)).isoformat() + " " + (today + timedelta(days=i)).strftime("%a") for i in range(1, 8)]
    out += "未来 7 天：" + "、".join(next7) + "\n"
    return ToolResult(True, out, display=f"📅 **{today.isoformat()}** 星期{['一','二','三','四','五','六','日'][today.weekday()]}")


# ---------- 2. 系统信息 ----------
def tool_sys_info(params: dict) -> ToolResult:
    try:
        mem = None
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                lines = f.read().strip().split("\n")
            kv = {}
            for l in lines[:5]:
                k, v = l.split(":")
                kv[k.strip()] = v.strip()
            total = int(kv["MemTotal"].split()[0]) / 1024
            free = int(kv["MemAvailable"].split()[0]) / 1024
            used = total - free
            mem = f"内存：{used:.0f}MB / {total:.0f}MB（{used/total*100:.0f}%）"
        disk = shutil.disk_usage("/") if os.path.isdir("/") else None
        loadavg = None
        if hasattr(os, "getloadavg"):
            loadavg = os.getloadavg()
        pyv = platform.python_version()
        plat = f"{platform.system()} {platform.release()} ({platform.machine()})"
        out = []
        out.append(f"系统：{plat}")
        out.append(f"Python：{pyv}")
        out.append(f"主机名：{platform.node()}")
        if mem: out.append(mem)
        if disk:
            d = f"磁盘 /：{disk.used/1024**3:.1f}GB / {disk.total/1024**3:.1f}GB（{disk.used/disk.total*100:.0f}%）"
            out.append(d)
        if loadavg: out.append(f"负载：{loadavg[0]:.2f} / {loadavg[1]:.2f} / {loadavg[2]:.2f}（1/5/15 分钟）")
        out.append(f"进程数：约 {len(os.listdir('/proc')) if os.path.isdir('/proc') else 'N/A'}")
        txt = "\n".join(out)
        return ToolResult(True, txt, display="💻 **系统诊断完成**\n```\n" + txt + "\n```")
    except Exception as e:
        return ToolResult(False, str(e), display=f"❌ 读取失败：{e}")


# ---------- 3. 天气（wttr.in，不耗 Key）----------
async def tool_weather(params: dict) -> ToolResult:
    city = (params.get("city") or "Beijing").strip() or "Beijing"
    # 中文地名转成 URL 编码
    from urllib.parse import quote
    url = f"https://wttr.in/{quote(city)}?format=j1&lang=zh"
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(url, headers={"User-Agent": "curl/8.0"})
        if r.status_code != 200:
            return ToolResult(False, f"天气服务返回 {r.status_code}", display=f"🌤 查不到「{city}」的天气")
        data = r.json()
        cur = data["current_condition"][0]
        today = data["weather"][0]
        desc = cur["lang_zh"][0]["value"] if cur.get("lang_zh") else cur["weatherDesc"][0]["value"]
        tmp_c = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        hum = cur["humidity"]
        wind = cur["windspeedKmph"]
        maxT = today["maxtempC"]
        minT = today["mintempC"]
        sun_h = today.get("astronomy", [{}])[0].get("sunrise", "?")
        sun_s = today.get("astronomy", [{}])[0].get("sunset", "?")
        out = (
            f"城市：{city}\n"
            f"天气：{desc}\n"
            f"温度：{tmp_c}°C（体感 {feels}°C）\n"
            f"今日：{minT}°C ~ {maxT}°C\n"
            f"湿度：{hum}% · 风速：{wind} km/h\n"
            f"日出 {sun_h} · 日落 {sun_s}"
        )
        disp = (
            f"🌤 **{city} 天气**\n"
            f"> {desc}，当前 **{tmp_c}°C**（体感 {feels}°C）\n"
            f"> 今日区间 **{minT} ~ {maxT}°C** · 湿度 {hum}% · 风速 {wind}km/h"
        )
        return ToolResult(True, out, display=disp)
    except Exception as e:
        return ToolResult(False, str(e), display=f"🌤 天气查询失败：{e}")


# ---------- 4. 计算器 ----------
def tool_calc(params: dict) -> ToolResult:
    expr = (params.get("expr") or "").strip()
    if not expr:
        return ToolResult(False, "空表达式", display="❌ 请给个算式")
    # 安全 eval：只允许数字、运算符、数学常量/函数
    allowed = set("0123456789+-*/().%^eE ,")
    safe_dict = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "abs": abs, "round": round,
        "pow": pow, "ceil": math.ceil, "floor": math.floor,
    }
    # 把 ^ 换成 **
    expr_py = expr.replace("^", "**")
    for ch in expr_py:
        if ch.isalpha():
            continue  # 允许函数名
        if ch not in allowed:
            return ToolResult(False, f"非法字符 {ch}", display=f"❌ 表达式里有不允许的字符：`{ch}`")
    try:
        result = eval(expr_py, {"__builtins__": {}}, safe_dict)
        out = f"{expr} = {result}"
        return ToolResult(True, out, display=f"🧮 `{expr}` = **{result}**")
    except Exception as e:
        return ToolResult(False, str(e), display=f"❌ 计算失败：{e}")


# ---------- 5. 读文件（白名单路径）----------
def tool_read_file(params: dict) -> ToolResult:
    path = os.path.abspath(os.path.expanduser(params.get("path", "")))
    if not any(path.startswith(p) for p in ALLOWED_READ_PREFIXES):
        return ToolResult(False, f"路径 {path} 不在允许范围", display=f"🔒 出于安全，不允许读这个路径")
    if not os.path.isfile(path):
        return ToolResult(False, f"文件不存在：{path}", display=f"📄 找不到文件 `{path}`")
    try:
        size = os.path.getsize(path)
        if size > 500 * 1024:
            return ToolResult(False, f"文件太大 {size} 字节", display="📄 文件超过 500KB，不给读")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        head = "".join(lines[:200])
        out = f"文件：{path}\n大小：{size} 字节 · {len(lines)} 行\n\n" + head
        disp = f"📄 **{os.path.basename(path)}**（{len(lines)} 行，前 200 行）\n```\n{head[:3000]}\n```"
        return ToolResult(True, out, display=disp)
    except Exception as e:
        return ToolResult(False, str(e), display=f"📄 读取失败：{e}")


# ---------- 6. 列出目录 ----------
def tool_list_dir(params: dict) -> ToolResult:
    path = os.path.abspath(os.path.expanduser(params.get("path", "~")))
    if not any(path.startswith(p) for p in ALLOWED_READ_PREFIXES):
        return ToolResult(False, f"路径 {path} 不在允许范围", display=f"🔒 不允许列这个路径")
    if not os.path.isdir(path):
        return ToolResult(False, f"不是目录：{path}", display=f"📁 `{path}` 不是目录")
    try:
        items = sorted(os.listdir(path))
        rows = []
        for name in items[:80]:
            fp = os.path.join(path, name)
            if os.path.isdir(fp):
                rows.append(f"  📁 {name}/")
            else:
                try:
                    sz = os.path.getsize(fp)
                    unit = "B" if sz < 1024 else ("KB" if sz < 1024*1024 else "MB")
                    v = sz if sz < 1024 else (sz/1024 if sz < 1024*1024 else sz/1024/1024)
                    rows.append(f"  📄 {name:<40} {v:.1f}{unit}")
                except Exception:
                    rows.append(f"  📄 {name}")
        out = f"目录：{path}\n共 {len(items)} 项\n" + "\n".join(rows)
        disp = f"📁 **{path}**（{len(items)} 项）\n```\n" + "\n".join(rows[:80]) + ("\n...更多已省略" if len(items) > 80 else "") + "\n```"
        return ToolResult(True, out, display=disp)
    except Exception as e:
        return ToolResult(False, str(e), display=f"📁 失败：{e}")


# ---------- 7. 安全 shell ----------
def tool_safe_shell(params: dict) -> ToolResult:
    cmd_key = (params.get("command") or "").strip()
    actual = SAFE_SHELL_WHITELIST.get(cmd_key)
    if actual is None:
        # 尝试模糊匹配，看看 cmd_key 是 whitelist 的键
        if cmd_key not in SAFE_SHELL_WHITELIST:
            return ToolResult(
                False,
                f"命令「{cmd_key}」不在白名单。允许的有：{', '.join(SAFE_SHELL_WHITELIST.keys())}",
                display=f"🔒 「{cmd_key}」不安全，不执行\n> 允许的命令：{', '.join(SAFE_SHELL_WHITELIST.keys())}"
            )
        actual = cmd_key
    import subprocess
    try:
        r = subprocess.run(actual, shell=True, capture_output=True, text=True, timeout=10)
        out = f"$ {actual}\n退出码 {r.returncode}\n\n"
        if r.stdout: out += "--- STDOUT ---\n" + r.stdout[:4000] + ("\n...截断" if len(r.stdout) > 4000 else "") + "\n"
        if r.stderr: out += "--- STDERR ---\n" + r.stderr[:2000] + ("\n...截断" if len(r.stderr) > 2000 else "") + "\n"
        disp = f"⌨️ `{actual}`\n```\n" + (r.stdout + r.stderr)[:3000] + "\n```"
        return ToolResult(True, out.strip(), display=disp)
    except Exception as e:
        return ToolResult(False, str(e), display=f"⌨️ 执行失败：{e}")


# ---------- 8. 倒计时 / 定时器（用户说「5 分钟后提醒我 XX」）----------
# 注意：真正执行在 brain.py 的 APScheduler 里，这里只负责把提醒写进 reminders 表
# 这里只做一个简单的「计时阻塞到点返回」版本用于同步测试
def tool_timer(params: dict) -> ToolResult:
    try:
        minutes = max(0.1, float(params.get("minutes", 0)))
    except (TypeError, ValueError):
        return ToolResult(False, "minutes 必须是数字", display="⏰ 请给有效的分钟数")
    note = params.get("note") or "（未写内容）"
    seconds = int(minutes * 60)
    # 不真的阻塞；只返回「我已经给你记住了，到点会提醒你」
    out = (
        f"提醒已登记：{minutes} 分钟后（{seconds} 秒）\n"
        f"内容：{note}\n"
        f"（系统将在 {(datetime.now() + timedelta(seconds=seconds)).strftime('%H:%M:%S')} 弹出提醒）"
    )
    disp = f"⏰ **已登记提醒**：{minutes:.1f} 分钟后 → {note}\n> 到点时间：{(datetime.now() + timedelta(seconds=seconds)).strftime('%H:%M:%S')}"
    return ToolResult(True, out, display=disp)


# ---------- 9. 所有已注册工具列表（用户问「你能做什么？」）----------
def tool_list_commands(params: dict, registry: ToolRegistry) -> ToolResult:
    rows = registry.list_all()
    cats: dict[str, list] = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    out_lines = []
    disp_lines = ["### 🛠 我可用的工具清单\n"]
    cat_label = {"general": "🧭 通用", "system": "💻 系统", "info": "📡 信息查询", "reminder": "⏰ 提醒"}
    for cat, items in cats.items():
        out_lines.append(f"[{cat_label.get(cat, cat)}]")
        disp_lines.append(f"**{cat_label.get(cat, cat)}**  ")
        for it in items:
            status = "✅" if it["enabled"] else "🚫"
            out_lines.append(f"- {it['name']}：{it['description']}")
            disp_lines.append(f"{status} `{it['name']}` — {it['description']}  ")
    out = "\n".join(out_lines)
    disp = "\n".join(disp_lines)
    return ToolResult(True, out, display=disp)


# ============================================================
#  构建 & 注册所有工具
# ============================================================
def build_registry() -> ToolRegistry:
    r = ToolRegistry()

    r.register(ToolMeta(
        "get_time", "获取当前本地时间（含日期、星期、时区、Unix 时间戳）", {},
        ["现在几点？", "今天几号"], category="info",
    ), tool_get_time)

    r.register(ToolMeta(
        "get_date", "获取今天日期+星期+未来7天", {},
        ["今天星期几？", "给我看下这周的日期"], category="info",
    ), tool_get_date)

    r.register(ToolMeta(
        "sys_info", "读取本机 CPU/内存/磁盘/负载/系统版本等整体状态", {},
        ["系统状态怎么样", "服务器资源使用率"], category="system",
    ), tool_sys_info)

    r.register(ToolMeta(
        "weather",
        "查询全球城市当前天气（通过 wttr.in，免 Key）。没写城市默认北京。",
        {"city": {"type": "string", "desc": "城市中文名或英文名，例如 上海 / Tokyo / New York", "required": False}},
        ["北京天气怎么样？", "上海明天会下雨吗", "纽约气温"], category="info",
    ), tool_weather)

    r.register(ToolMeta(
        "calc",
        "安全的数学计算器。支持 + - * / % ^、括号、sin/cos/tan/sqrt/log/pi/e/abs/ceil/floor/round/pow",
        {"expr": {"type": "string", "desc": "要计算的表达式，例如 2^10、sin(pi/2)、sqrt(144)", "required": True}},
        ["根号 144 等于多少", "2 的 10 次方", "帮我算 sin(pi/6)"], category="general",
    ), tool_calc)

    r.register(ToolMeta(
        "read_file",
        "读取本地文本文件（只读，且仅允许在项目目录和用户家目录下）。文件最大 500KB，返回前 200 行。",
        {"path": {"type": "string", "desc": "要读的文件路径，支持 ~ 展开，例如 ~/notes.txt 或 ./backend/requirements.txt", "required": True}},
        ["帮我看下 requirements.txt 都有什么依赖", "读一下我的笔记"], category="system",
        dangerous=True,
    ), tool_read_file)

    r.register(ToolMeta(
        "list_dir",
        "列出本地目录内容（仅允许项目目录和用户家目录）。不传 path 就列用户家目录。",
        {"path": {"type": "string", "desc": "目录路径，支持 ~，不传默认 ~", "required": False}},
        ["项目目录下都有什么？", "列一下我家目录"], category="system",
        dangerous=True,
    ), tool_list_dir)

    r.register(ToolMeta(
        "safe_shell",
        "执行安全白名单里的 shell 命令。不在白名单的一律拒绝。",
        {"command": {"type": "string", "desc": "必须是白名单里的完整字符串：date / uptime / whoami / uname -a / df -h / free -h / top -bn1 | head -20", "required": True}},
        ["查看开机多久了", "磁盘使用率", "当前登录的用户"], category="system",
    ), tool_safe_shell)

    r.register(ToolMeta(
        "timer",
        "登记一个倒计时提醒。过 N 分钟后，我会主动弹消息提醒你做某件事。",
        {
            "minutes": {"type": "number", "desc": "多少分钟后，可以是小数，例如 0.5（30 秒）、5、30、120", "required": True},
            "note": {"type": "string", "desc": "要提醒的内容，例如「开会」「吃药」「起来走走」", "required": True},
        },
        ["5 分钟后提醒我开会", "半小时后叫我吃药", "明天早上 8 点提醒我起床"], category="reminder",
    ), tool_timer)

    return r


# ============================================================
#  ToolExecutor：LLM 选工具 + 解析参数 + 执行
# ============================================================
class ToolExecutor:
    """负责：问 LLM → 解析 JSON → 调工具 → 返回 ToolResult"""

    def __init__(self, registry: ToolRegistry, llm):
        self.registry = registry
        self.llm = llm

    async def plan_and_run(
        self,
        user_text: str,
        *,
        extra_sys: str = "",
    ) -> Optional[ToolResult]:
        """
        让 LLM 判断要不要用工具、用哪个、参数是什么。
        不需要工具就返回 None。
        """
        sys_prompt = self.registry.format_for_llm()
        if extra_sys:
            sys_prompt += "\n【额外上下文】\n" + extra_sys + "\n"
        sys_prompt += (
            "\n【最终指令】"
            "\n现在根据用户的需求，严格输出一个 JSON："
            '\n能用工具 → {"tool": "工具名", "params": {...}}'
            '\n不需要 → {"tool": "", "params": {}}'
            "\nJSON 之外不要任何文字、不要 markdown、不要代码块包裹。"
        )
        t0 = time.time()
        try:
            raw = await self.llm.complete(
                user_text,
                system_prompt=sys_prompt,
                temperature=0.1,
                max_tokens=500,
            )
        except Exception as e:
            print(f"[JARVIS] 工具规划阶段 LLM 失败: {e}")
            return None

        raw = raw.strip()
        # 容错：去代码块
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw).rstrip("`").strip()
        # 容错：只取 {...} 部分
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            print(f"[JARVIS] LLM 没返回 JSON: {raw[:200]}")
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception as e:
            print(f"[JARVIS] 解析工具 JSON 失败: {e}；raw={raw[:200]}")
            return None
        tool_name = (obj.get("tool") or "").strip()
        if not tool_name:
            return None
        if not self.registry.is_enabled(tool_name):
            print(f"[JARVIS] 工具 {tool_name} 已禁用")
            return None
        meta, func = self.registry.get(tool_name)
        params = obj.get("params") or {}
        # 执行（支持同步函数和 async 函数）
        dur = int((time.time() - t0) * 1000)
        try:
            # 有一个工具需要 registry 注入
            if tool_name == "list_commands":
                out = func(params, self.registry)
            elif asyncio.iscoroutinefunction(func):
                out = await func(params)
            else:
                loop = asyncio.get_running_loop()
                out = await loop.run_in_executor(None, func, params)
        except Exception as e:
            out = ToolResult(False, f"工具执行异常: {e}", display=f"❌ 工具 `{tool_name}` 异常：{e}", tool_name=tool_name)
        if isinstance(out, ToolResult):
            out.tool_name = tool_name
            out.duration_ms += dur
        return out
