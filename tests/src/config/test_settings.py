import builtins
import importlib
import os
import unittest
from unittest.mock import patch

from src.config.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_environment_values_are_normalized_and_deduplicated(self):
        environment = {
            "ARTIFACTS_API_KEY": "test-key",
            "ARTIFACTS_API_BASE_URL": "https://game.test",
            "ARTIFACTS_CHARACTER_NAME": "TestCharacter",
            "LOG_LEVEL": "DEBUG",
            "MAX_RETRIES": "5",
            "REQUEST_TIMEOUT": "12",
            "COMBAT_FOOD_ALLOWLIST": " cooked_shrimp,,cooked_trout,cooked_shrimp ",
            "COMBAT_FOOD_COUNT": "4",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings()

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.api_base_url, "https://game.test")
        self.assertEqual(settings.character_name, "TestCharacter")
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.max_retries, 5)
        self.assertEqual(settings.request_timeout, 12)
        self.assertEqual(
            settings.combat_food_allowlist,
            ("cooked_shrimp", "cooked_trout"),
        )
        self.assertEqual(settings.combat_food_count, 4)
        settings.validate()

    def test_validation_rejects_missing_api_key_and_negative_food_count(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        with self.assertRaisesRegex(ValueError, "ARTIFACTS_API_KEY"):
            settings.validate()

        with patch.dict(
            os.environ,
            {
                "ARTIFACTS_API_KEY": "test-key",
                "COMBAT_FOOD_COUNT": "-1",
            },
            clear=True,
        ):
            settings = Settings()
        with self.assertRaisesRegex(ValueError, "COMBAT_FOOD_COUNT"):
            settings.validate()

    def test_repr_omits_api_key(self):
        with patch.dict(
            os.environ,
            {"ARTIFACTS_API_KEY": "must-not-appear"},
            clear=True,
        ):
            representation = repr(Settings())

        self.assertNotIn("must-not-appear", representation)
        self.assertIn("character_name=", representation)

    def test_dotenv_is_optional_when_import_is_unavailable(self):
        module = importlib.import_module("src.config.settings")
        original_settings = module.settings
        real_import = builtins.__import__

        def import_without_dotenv(name, *args, **kwargs):
            if name == "dotenv":
                raise ImportError("optional dependency unavailable")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=import_without_dotenv):
                importlib.reload(module)
            with patch.dict(os.environ, {"ARTIFACTS_API_KEY": "test-key"}, clear=True):
                settings = module.Settings()
            settings.validate()
        finally:
            module.settings = original_settings


if __name__ == "__main__":
    unittest.main()
