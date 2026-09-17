import datetime as dt
import unittest

from cli.macos_bridge import build_catalog, normalize_request


class MacOSBridgeTests(unittest.TestCase):
    def test_catalog_exposes_provider_and_language_metadata(self):
        catalog = build_catalog()

        provider_values = {provider["value"] for provider in catalog["providers"]}
        language_values = {language["value"] for language in catalog["output_languages"]}

        self.assertIn("openai", provider_values)
        self.assertIn("openrouter", provider_values)
        self.assertIn("ollama_cloud", provider_values)
        self.assertIn("custom", language_values)

    def test_catalog_mirrors_cli_provider_table(self):
        from cli.utils import _llm_provider_table

        providers = {provider["value"]: provider for provider in build_catalog()["providers"]}

        self.assertEqual(list(providers), [value for _, value, _ in _llm_provider_table()])
        for provider in providers.values():
            models = provider["quick_models"] + provider["deep_models"]
            self.assertNotIn("custom", [model["value"] for model in models])
        self.assertFalse(providers["ollama_cloud"]["supports_custom_models"])
        for value in ("openrouter", "azure", "groq", "openai_compatible"):
            self.assertTrue(providers[value]["supports_custom_models"])

    def test_normalize_request_orders_analysts_and_applies_provider_default_url(self):
        today = dt.date.today().isoformat()
        request = normalize_request(
            {
                "ticker": " spy ",
                "analysis_date": today,
                "analysts": ["news", "market"],
                "research_depth": 3,
                "llm_provider": "openai",
                "shallow_thinker": "gpt-5.4-mini",
                "deep_thinker": "gpt-5.4",
                "output_language": "English",
            }
        )

        self.assertEqual(request.ticker, "SPY")
        self.assertEqual(request.analysts, ["market", "news"])
        self.assertEqual(request.backend_url, "https://api.openai.com/v1")

    def test_normalize_request_rejects_future_dates(self):
        future_date = (dt.date.today() + dt.timedelta(days=1)).isoformat()

        with self.assertRaisesRegex(ValueError, "future"):
            normalize_request(
                {
                    "ticker": "SPY",
                    "analysis_date": future_date,
                    "analysts": ["market"],
                    "research_depth": 1,
                    "llm_provider": "openai",
                    "shallow_thinker": "gpt-5.4-mini",
                    "deep_thinker": "gpt-5.4",
                    "output_language": "English",
                }
            )


if __name__ == "__main__":
    unittest.main()
