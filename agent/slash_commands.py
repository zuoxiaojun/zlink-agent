"""Slash-command system for YS-Agent.

Commands are triggered when a user message starts with "/".  They execute
locally (no LLM call) and return a result directly to the UI.

Add new commands by decorating a handler with ``@register_command(...)``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SlashCommand:
    name: str
    description: str
    usage: str
    handler: Callable[[str, dict], str]


_registry: dict[str, SlashCommand] = {}


def register_command(name: str, description: str, usage: str = ""):
    """Decorator: register a slash-command handler.

    The handler receives ``(args_string: str, context: dict)`` where
    *context* carries ``config``, ``session_id``, ``token_usage``, etc.
    """

    def dec(fn: Callable[[str, dict], str]):
        _registry[name] = SlashCommand(
            name=name,
            description=description,
            usage=usage or f"/{name}",
            handler=fn,
        )
        return fn

    return dec


def parse_command(message: str) -> tuple[str, str] | None:
    """If *message* starts with '/', return (command_name, args_string)."""
    stripped = message.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


def get_command(name: str) -> SlashCommand | None:
    return _registry.get(name)


def list_commands() -> list[SlashCommand]:
    return sorted(_registry.values(), key=lambda c: c.name)


def execute(command_name: str, args: str, context: dict) -> str | None:
    """Run a slash command and return its result.  Returns None if unknown."""
    cmd = _registry.get(command_name)
    if cmd is None:
        return None
    try:
        return cmd.handler(args, context)
    except Exception as e:
        logger.exception("Slash command /%s failed", command_name)
        return f"命令执行失败: {e}"


# ---- built-in commands -------------------------------------------------------


@register_command("help", "显示所有可用命令", "/help")
def _cmd_help(_args: str, _ctx: dict) -> str:
    lines = ["## 可用命令\n"]
    for cmd in list_commands():
        lines.append(f"- **/{cmd.name}** {cmd.usage} — {cmd.description}")
    return "\n".join(lines)


@register_command("model", "切换 LLM 模型", "/model <模型名>")
def _cmd_model(args: str, ctx: dict) -> str:
    if not args.strip():
        cfg = ctx.get("config", {})
        current = cfg.get("llm_model", "未知")
        manual_override = cfg.get("max_context_tokens", 0)
        from agent.context_compactor import resolve_context_window

        if manual_override > 0:
            window = manual_override
            source = "（手动设置）"
        else:
            window = resolve_context_window(current)
            source = "（自动检测）"
        return (
            f"当前模型: **{current}**\n"
            f"上下文窗口: **{window:,} tokens** {source}\n\n"
            f"用法: `/model <模型名>`\n\n"
            f"可在 LLM 配置页面查看可用模型列表。"
        )

    from agent import config_manager

    cfg = config_manager.load()
    new_model = args.strip()
    cfg.llm_model = new_model
    config_manager.save(cfg)
    return f"已切换到模型: **{new_model}**\n\n刷新页面后生效，新对话将使用此模型。"


@register_command("compact", "手动触发上下文压缩", "/compact")
def _cmd_compact(_args: str, ctx: dict) -> str:
    try:
        session_id = ctx.get("session_id", "")
        if not session_id:
            return "当前没有活动会话。"
        # Signal the agent to compact on next turn — for now, simple advisory
        return (
            "上下文压缩将在下一轮对话时自动触发（如果消息量超过阈值）。\n\n"
            "你可以在 **Agent 设置** 中调整压缩参数：\n"
            "- 关闭/开启自动压缩\n"
            "- 调整上下文窗口大小\n"
            "- 调整保留的最近对话量"
        )
    except Exception as e:
        return f"压缩失败: {e}"


@register_command("clear", "清空当前会话开始新对话", "/clear")
def _cmd_clear(_args: str, ctx: dict) -> str:
    return "__YS_CLEAR_SESSION__"


@register_command("login", "显示 API Key 配置指引", "/login [供应商名]")
def _cmd_login(args: str, _ctx: dict) -> str:
    target = args.strip().lower() if args.strip() else ""
    providers = {
        "openai": ("OpenAI", "https://platform.openai.com/api-keys", "sk-..."),
        "deepseek": ("DeepSeek", "https://platform.deepseek.com/api-keys", "sk-..."),
        "anthropic": ("Anthropic", "https://console.anthropic.com/keys", "sk-ant-..."),
        "kimi": ("Kimi (月之暗面)", "https://platform.moonshot.cn/console/api-keys", "sk-kimi-..."),
        "glm": ("智谱 GLM", "https://open.bigmodel.cn/usercenter/apikeys", ""),
        "qwen": ("阿里通义千问", "https://dashscope.console.aliyun.com/apiKey", "sk-..."),
        "siliconflow": ("硅基流动", "https://cloud.siliconflow.cn/account/ak", "sk-..."),
    }

    if target and target in providers:
        name, url, fmt = providers[target]
        return (
            f"## {name} API Key 配置\n\n"
            f"1. 前往 [{url}]({url}) 获取 API Key\n"
            f"2. 格式: `{fmt}`\n"
            f"3. 在 **LLM 配置** 页面填入 API Key、Base URL、选择模型\n"
        )

    lines = ["## 支持的 LLM 供应商\n"]
    for key, (name, url, _) in providers.items():
        lines.append(f"- **{name}**: `/login {key}`")
    lines.append("\n在 **LLM 配置** 页面填写 API Key 即可开始使用。")

    if target:
        return f"未找到供应商 '{target}'。\n\n" + "\n".join(lines)
    return "\n".join(lines)


@register_command("cost", "显示当前会话 Token 用量", "/cost")
def _cmd_cost(_args: str, ctx: dict) -> str:
    usage = ctx.get("token_usage")
    if not usage or usage.get("total_tokens", 0) == 0:
        return "当前会话暂无 Token 用量统计。"
    return (
        f"## Token 用量\n\n"
        f"| 类型 | Tokens |\n"
        f"|------|--------|\n"
        f"| 输入 | {usage.get('prompt_tokens', 0):,} |\n"
        f"| 输出 | {usage.get('completion_tokens', 0):,} |\n"
        f"| 合计 | {usage.get('total_tokens', 0):,} |\n"
    )
