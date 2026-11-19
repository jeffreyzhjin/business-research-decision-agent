"""Minimal real LLM connectivity check using the selected .env provider.

Usage: python -m scripts.test_llm_connection
Does not print secrets. Prints type and HTTP status for failed requests.
"""

import asyncio

from dotenv import load_dotenv

from src.llm_provider import create_llm_client, get_provider


async def main():
    load_dotenv()
    provider = get_provider()
    client, model_name = create_llm_client()
    print(f"Testing provider={provider}, model={model_name}")
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是测试助手。"},
                {"role": "user", "content": "请只回复：连接成功"},
            ],
            max_tokens=40,
        )
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        payload = getattr(exc, "body", None)
        details = payload if isinstance(payload, dict) else {}
        if isinstance(details.get("error"), dict):
            details = details["error"]
        code = details.get("code", "unknown")
        # Only report a fixed set of safe diagnostic fields.
        print(f"FAILED: {type(exc).__name__}, HTTP status={status or 'unknown'}")
        print(f"Provider error code: {str(code)[:120]}")
        # Avoid echoing response bodies, credentials, or request headers.
        print("Read Model Studio error-code docs for the reported code.")
        print("Check API Key model scope, workspace, service activation, billing and region.")
        return 1
    if not response.choices or not response.choices[0].message.content:
        print("FAILED: empty response")
        return 1
    print("PASS: model returned a nonempty response.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
