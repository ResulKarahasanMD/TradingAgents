import unittest
import warnings

import pytest

from tradingagents.llm_clients.base_client import BaseLLMClient
from tradingagents.llm_clients.model_catalog import get_known_models, get_model_options
from tradingagents.llm_clients.validators import validate_model

OLLAMA_CLOUD_MODELS = [
    "deepseek-v4.1-flash",
    "glm-5.3-flash",
    "glm-5.3",
    "kimi-k3",
    "glm-5.2",
    "kimi-k2.7-code",
    "nemotron-3-ultra",
    "minimax-m3",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "glm-5.1",
    "kimi-k2.6",
    "minimax-m2.7",
    "gemma4:31b",
    "nemotron-3-super",
    "qwen3.5:397b",
    "nemotron-3-nano:30b",
    "mistral-large-3:675b",
    "gpt-oss:20b",
    "gpt-oss:120b",
]


class DummyLLMClient(BaseLLMClient):
    def __init__(self, provider: str, model: str):
        self.provider = provider
        super().__init__(model)

    def get_llm(self):
        self.warn_if_unknown_model()
        return object()

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)


@pytest.mark.unit
class ModelValidationTests(unittest.TestCase):
    def test_cli_catalog_models_are_all_validator_approved(self):
        for provider, models in get_known_models().items():
            if provider in ("ollama", "ollama_cloud", "openrouter"):
                continue

            for model in models:
                with self.subTest(provider=provider, model=model):
                    self.assertTrue(validate_model(provider, model))

    def test_unknown_model_emits_warning_for_strict_provider(self):
        client = DummyLLMClient("openai", "not-a-real-openai-model")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.get_llm()

        self.assertEqual(len(caught), 1)
        self.assertIn("not-a-real-openai-model", str(caught[0].message))
        self.assertIn("openai", str(caught[0].message))

    def test_openrouter_and_ollama_accept_custom_models_without_warning(self):
        for provider in ("openrouter", "ollama", "ollama_cloud"):
            client = DummyLLMClient(provider, "custom-model-name")

            with self.subTest(provider=provider):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    client.get_llm()

                self.assertEqual(caught, [])


@pytest.mark.unit
class OllamaCloudCatalogTests(unittest.TestCase):
    def test_catalog_includes_each_cloud_model_once(self):
        self.assertEqual(len(OLLAMA_CLOUD_MODELS), len(set(OLLAMA_CLOUD_MODELS)))
        known = get_known_models()["ollama_cloud"]
        self.assertEqual(known, sorted(OLLAMA_CLOUD_MODELS))

    def test_quick_and_deep_lists_expose_all_cloud_models_without_duplicates(self):
        expected = set(OLLAMA_CLOUD_MODELS)
        for mode in ("quick", "deep"):
            values = [value for _, value in get_model_options("ollama_cloud", mode)]
            with self.subTest(mode=mode):
                self.assertEqual(len(values), len(set(values)))
                self.assertEqual(set(values), expected)
