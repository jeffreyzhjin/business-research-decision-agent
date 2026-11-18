"""Configurable LLM backend for mainland-China-friendly deployments.

The existing Groq backend remains the default for compatibility.
Set LLM_PROVIDER=bailian to use Alibaba Cloud Model Studio's OpenAI-
compatible Chat Completions API in the Beijing region.

Only the selected provider's API key is used; never log key material.
"""

import os

from dotenv import load_dotenv
from groq import AsyncGroq
from openai import AsyncOpenAI

load_dotenv()

VALID_PROVIDERS = {"groq", "bailian"}


def get_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            "Unsupported LLM_PROVIDER; select 'groq' or 'bailian'."
        )
    return provider


def get_api_key() -> str | None:
    env_name = (
        "DASHSCOPE_API_KEY" if get_provider() == "bailian"
        else "GROQ_API_KEY"
    )
    return os.getenv(env_name)


def has_llm_credentials() -> bool:
    return bool(get_api_key())


def get_model_name() -> str:
    provider = get_provider()
    default = (
        "qwen3.8-flash" if provider == "bailian"
        else "openai/gpt-oss-20b"
    )
    return os.getenv("LLM_MODEL", "").strip() or default


def create_llm_client():
    """Return (async client, model id) for the configured provider."""
    provider = get_provider()
    api_key = get_api_key()
    if not api_key:
        name = "DASHSCOPE_API_KEY" if provider == "bailian" else "GROQ_API_KEY"
        raise RuntimeError(f"Missing {name} for LLM_PROVIDER={provider}.")
    if provider == "bailian":
        # The standard Mainland China (Beijing) endpoint. Override only
        # with a legitimate regional/workspace endpoint for your account.
        base_url = os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        return AsyncOpenAI(
            api_key=api_key, base_url=base_url,
        ), get_model_name()
    return AsyncGroq(api_key=api_key), get_model_name()


def completion_options(max_tokens: int) -> dict:
    """Provider-specific options; avoid sending Groq-only arguments to Qwen."""
    if get_provider() == "bailian":
        return {
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
    return {
        "temperature": 0.1,
        "reasoning_effort": "low",
        "max_completion_tokens": max_tokens,
    }
