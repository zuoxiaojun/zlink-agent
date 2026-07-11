"""Vision analysis tool — describe and analyze images using LLM vision.

Analyses images using the configured LLM's vision capability. Supports:
- Image URLs (publicly accessible)
- Base64-encoded data URIs (inline images)

Requires the LLM provider to support vision (multi-modal) inputs.
"""

import base64
import json
import logging
import re

import httpx

from agent.tools.registry import registry

logger = logging.getLogger(__name__)


def _is_data_uri(url: str) -> bool:
    return url.startswith("data:image/")


def _image_to_base64(url: str) -> str | None:
    """Download an image URL and return base64 encoded data."""
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            b64 = base64.b64encode(resp.content).decode("ascii")
            return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning("Failed to download image: %s", e)
        return None


def vision_analyze_tool(image_url: str, question: str = "") -> str:
    """Analyze an image using the LLM's vision capability.

    Args:
        image_url: URL to the image or data: URI
        question: Optional question about the image

    Returns:
        JSON with analysis result or error
    """
    if not image_url:
        return json.dumps({"error": "image_url is required"})

    # Normalize to data URI
    data_uri = image_url if _is_data_uri(image_url) else _image_to_base64(image_url)
    if data_uri is None:
        return json.dumps({"error": "无法下载图片，请确保图片可公开访问"})

    # Use the configured LLM to analyze the image
    try:
        from agent import config_manager

        cfg = config_manager.load()
        api_key = cfg.llm_api_key
        base_url = cfg.llm_base_url
        model = cfg.llm_model

        if not api_key:
            return json.dumps({"error": "未配置 LLM API Key"})

        # Build vision message
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question or "请详细描述这张图片的内容"},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                ],
            }
        ]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # Determine API endpoint (handle OpenAI-compatible and DeepSeek)
        api_url = base_url.rstrip("/")
        if "/chat/completions" not in api_url:
            api_url += "/chat/completions"

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = ""
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "")

        if not content:
            return json.dumps({"error": "LLM 未返回分析结果"})

        return json.dumps({"analysis": content}, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"API 请求失败: {e.response.status_code}"})
    except httpx.TimeoutException:
        return json.dumps({"error": "API 请求超时"})
    except Exception as e:
        logger.exception("Vision analysis failed")
        return json.dumps({"error": f"分析失败: {e}"})


VISION_ANALYZE_SCHEMA = {
    "name": "vision_analyze",
    "description": (
        "分析图片内容。支持公开图片 URL 或 base64 data URI。"
        "可以要求 AI 描述图片、识别图中的文字、分析图表或截图等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_url": {
                "type": "string",
                "description": "图片 URL（公开可访问）或 data: URI",
            },
            "question": {
                "type": "string",
                "description": "关于图片的问题，如'这张图表显示什么趋势？'不填则默认要求详细描述",
            },
        },
        "required": ["image_url"],
    },
}

registry.register(
    name="vision_analyze",
    toolset="vision",
    schema=VISION_ANALYZE_SCHEMA,
    handler=lambda args, **kw: vision_analyze_tool(
        image_url=args.get("image_url", ""),
        question=args.get("question", ""),
    ),
    description="分析图片内容（描述、识别文字、分析图表等）",
    emoji="👁️",
    risk_level="low",
)
