import os
import runpy
import sys
import unittest
from unittest.mock import patch

from tests.fake_game_api import FakeGameAPI
from src.config.settings import settings


class ScriptTestCase(unittest.TestCase):
    def setUp(self):
        self.api = FakeGameAPI()

    def run_script(self, module, args, environment=None):
        with (
            patch.object(module, "APIClient", return_value=self.api),
            patch.object(sys, "argv", [module.__file__, *args]),
            patch.multiple(
                settings,
                api_key="test-key",
                character_name="tester",
                combat_food_allowlist=(),
                combat_food_count=0,
            ),
            patch.dict(os.environ, environment or {}),
        ):
            return module.main()

    def run_as_entrypoint_without_configuration(self, module):
        with (
            patch.object(settings, "validate", side_effect=ValueError("bad config")),
            patch.object(sys, "argv", [module.__file__]),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(module.__file__, run_name="__main__")

        self.assertEqual(raised.exception.code, 1)
