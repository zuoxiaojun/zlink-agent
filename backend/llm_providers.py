"""LLM provider definitions — single source of truth shared by backend and app.py.

The ``protocol`` field picks which provider class to use:

* ``"openai_compat"`` — OpenAI Chat Completions protocol.  Covers most
  Chinese / third-party hosts.
* ``"anthropic"``     — Anthropic native Messages API.
* ``"baidu_qianfan"`` — Baidu Qianfan custom (not OpenAI-compat).

The factory in :mod:`agent.core.llm_providers.factory` reads this field
and instantiates the right class.  Adding a new provider only requires
adding an entry here — no Python code changes.
"""

LLM_PROVIDERS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o3", "o4-mini"],
        "api_key_label": "OpenAI API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-v3"],
        "api_key_label": "DeepSeek API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "Anthropic": {
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-latest"],
        "api_key_label": "Anthropic API Key",
        "api_key_placeholder": "sk-ant-...",
        "protocol": "anthropic",
    },
    "Kimi (Moonshot)": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["kimi-k2.5", "kimi-latest"],
        "api_key_label": "Kimi API Key",
        "api_key_placeholder": "sk-kimi-...",
        "protocol": "openai_compat",
    },
    "智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
        "api_key_label": "智谱 AI API Key",
        "api_key_placeholder": "",
        "protocol": "openai_compat",
    },
    "阿里通义千问 (Qwen)": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-coder-plus", "qwen-coder-turbo"],
        "api_key_label": "阿里云 DashScope API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "硅基流动 (SiliconFlow)": {
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Pro/Qwen/Qwen2.5-7B-Instruct"],
        "api_key_label": "SiliconFlow API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4", "deepseek/deepseek-chat", "qwen/qwen-coder-plus"],
        "api_key_label": "OpenRouter API Key",
        "api_key_placeholder": "sk-or-...",
        "protocol": "openai_compat",
    },
    "百度千帆 (ERNIE)": {
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "models": ["ernie-4.0", "ernie-3.5"],
        "api_key_label": "百度 API Key",
        "api_key_placeholder": "",
        # Baidu uses a custom protocol — kept as a separate type so
        # adding a new Baidu-specific class doesn't touch the openai_compat path.
        "protocol": "baidu_qianfan",
    },
    "MiniMax": {
        "base_url": "https://api.minimaxi.com/v1",
        "models": ["MiniMax-M2.5-70B", "MiniMax-Text-01"],
        "api_key_label": "MiniMax API Key",
        "api_key_placeholder": "",
        "protocol": "openai_compat",
    },
}
