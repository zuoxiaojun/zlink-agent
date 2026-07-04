LLM_PROVIDERS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "models": [
            {"id": "gpt-4o", "context_length": 128000},
            {"id": "gpt-4o-mini", "context_length": 128000},
            {"id": "gpt-4.1", "context_length": 1000000, "max_output": 8192},
            {"id": "gpt-4.1-mini", "context_length": 1000000, "max_output": 8192},
            {"id": "gpt-4.1-nano", "context_length": 1000000, "max_output": 8192},
            {"id": "o3", "context_length": 200000, "max_output": 100000},
            {"id": "o4-mini", "context_length": 200000, "max_output": 100000},
        ],
        "api_key_label": "OpenAI API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models": [
            {"id": "deepseek-v4-flash", "context_length": 1000000, "max_output": 384000},
            {"id": "deepseek-v4-pro", "context_length": 1000000},
        ],
        "api_key_label": "DeepSeek API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "Anthropic": {
        "base_url": "https://api.anthropic.com",
        "models": [
            {"id": "claude-sonnet-4-20250514", "context_length": 200000},
            {"id": "claude-3-5-haiku-latest", "context_length": 200000},
        ],
        "api_key_label": "Anthropic API Key",
        "api_key_placeholder": "sk-ant-...",
        "protocol": "anthropic",
    },
    "Kimi (Moonshot)": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": [
            {"id": "kimi-k2.5", "context_length": 128000},
            {"id": "kimi-latest", "context_length": 128000},
        ],
        "api_key_label": "Kimi API Key",
        "api_key_placeholder": "sk-kimi-...",
        "protocol": "openai_compat",
    },
    "智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            {"id": "glm-4-plus", "context_length": 128000},
            {"id": "glm-4-air", "context_length": 128000},
            {"id": "glm-4-flash", "context_length": 128000},
        ],
        "api_key_label": "智谱 AI API Key",
        "api_key_placeholder": "",
        "protocol": "openai_compat",
    },
    "阿里通义千问 (Qwen)": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            {"id": "qwen-plus", "context_length": 1000000},
            {"id": "qwen-turbo", "context_length": 1000000},
            {"id": "qwen-max", "context_length": 1000000},
            {"id": "qwen-coder-plus", "context_length": 1000000},
            {"id": "qwen-coder-turbo", "context_length": 128000},
        ],
        "api_key_label": "阿里云 DashScope API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "硅基流动 (SiliconFlow)": {
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            {"id": "Qwen/Qwen2.5-72B-Instruct", "context_length": 128000},
            {"id": "deepseek-ai/DeepSeek-V3", "context_length": 128000},
            {"id": "deepseek-ai/DeepSeek-R1", "context_length": 128000},
            {"id": "Pro/Qwen/Qwen2.5-7B-Instruct", "context_length": 32768},
        ],
        "api_key_label": "SiliconFlow API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            {"id": "openai/gpt-4o", "context_length": 128000},
            {"id": "anthropic/claude-sonnet-4", "context_length": 200000},
            {"id": "deepseek/deepseek-chat", "context_length": 1000000},
            {"id": "qwen/qwen-coder-plus", "context_length": 1000000},
        ],
        "api_key_label": "OpenRouter API Key",
        "api_key_placeholder": "sk-or-...",
        "protocol": "openai_compat",
    },
    "MiniMax": {
        "base_url": "https://api.minimaxi.com/v1",
        "models": [
            {"id": "MiniMax-M2.5-70B", "context_length": 128000},
            {"id": "MiniMax-Text-01", "context_length": 1000000},
        ],
        "api_key_label": "MiniMax API Key",
        "api_key_placeholder": "",
        "protocol": "openai_compat",
    },
}

_VISION_MODELS: list[str] = [
    "gpt-4o",
    "gpt-4.1",
    "o3",
    "o4-mini",
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-3-5",
    "claude-3-opus",
    "gemini-2.5",
    "gemini-2.0",
    "gemini-1.5",
    "qwen-vl",
    "qwen2.5-vl",
    "qvq",
    "kimi-k2",
    "kimi-latest",
    "glm-4v",
    "minimax-m2",
]


def model_supports_vision(model_id: str) -> bool:
    if not model_id:
        return False
    lowered = model_id.lower()
    for pattern in _VISION_MODELS:
        if pattern.lower() in lowered:
            return True
    return False
