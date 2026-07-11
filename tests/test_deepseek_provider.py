"""Tests for DeepSeek provider configuration."""

from backend.llm_providers import LLM_PROVIDERS


def test_deepseek_entry_exists():
    """DeepSeek must be present in LLM_PROVIDERS with correct structure."""
    assert "DeepSeek" in LLM_PROVIDERS
    entry = LLM_PROVIDERS["DeepSeek"]
    assert entry["protocol"] == "openai_compat"
    assert entry["base_url"] == "https://api.deepseek.com"


def test_deepseek_has_required_models():
    """DeepSeek must include all four required models."""
    models = [m["id"] for m in LLM_PROVIDERS["DeepSeek"]["models"]]
    assert len(models) == 4
    assert "deepseek-chat" in models
    assert "deepseek-reasoner" in models
    assert "deepseek-v4-flash" in models
    assert "deepseek-v4-pro" in models


def test_deepseek_models_have_context_length():
    """Each DeepSeek model must specify context_length."""
    for model in LLM_PROVIDERS["DeepSeek"]["models"]:
        assert "context_length" in model
        assert model["context_length"] > 0
