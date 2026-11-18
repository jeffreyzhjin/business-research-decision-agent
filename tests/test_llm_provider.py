"""Provider configuration checks; these tests never make network requests."""

import os
import unittest
from unittest.mock import patch

from openai import AsyncOpenAI
from groq import AsyncGroq

from src.llm_provider import (
    completion_options,
    create_llm_client,
    get_api_key,
    get_model_name,
    get_provider,
)


class LlmProviderTests(unittest.TestCase):
    def test_existing_groq_provider_remains_default(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "groq",
            "GROQ_API_KEY": "testing-key",
            "LLM_MODEL": "",
        }):
            self.assertEqual(get_provider(), "groq")
            client, model = create_llm_client()
            self.assertIsInstance(client, AsyncGroq)
            self.assertEqual(model, "openai/gpt-oss-20b")
            self.assertIn("reasoning_effort", completion_options(500))

    def test_bailian_uses_china_endpoint(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "bailian",
            "DASHSCOPE_API_KEY": "testing-key",
            "DASHSCOPE_BASE_URL":
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "LLM_MODEL": "",
        }):
            self.assertEqual(get_api_key(), "testing-key")
            client, model = create_llm_client()
            self.assertIsInstance(client, AsyncOpenAI)
            self.assertEqual(model, "qwen-plus")
            self.assertEqual(
                str(client.base_url),
                "https://dashscope.aliyuncs.com/compatible-mode/v1/",
            )
            opts = completion_options(500)
            self.assertEqual(opts["max_tokens"], 500)
            self.assertNotIn("reasoning_effort", opts)

    def test_missing_selected_key(self):
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "bailian",
            "DASHSCOPE_API_KEY": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "DASHSCOPE_API_KEY"):
                create_llm_client()

    def test_unknown_provider_rejected(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}):
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                get_provider()


if __name__ == "__main__":
    unittest.main()
