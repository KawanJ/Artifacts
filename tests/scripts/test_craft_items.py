from unittest.mock import patch

from scripts import craft_items
from tests.script_test_support import ScriptTestCase
from src.config.settings import settings


class CraftItemsScriptTests(ScriptTestCase):
    def test_script_acquires_ingredients_and_keeps_crafted_output(self):
        result = self.run_script(craft_items, ["wooden_staff", "2"])

        self.assertEqual(result, 0)
        self.assertEqual(self.api.gathered, {"copper_ore": 2})
        self.assertEqual(self.api.inventory, {"wooden_staff": 2})

    def test_missing_or_invalid_arguments_are_rejected(self):
        self.assertEqual(self.run_script(craft_items, []), 1)
        self.assertEqual(
            self.run_script(craft_items, ["wooden_staff", "not-a-number"]),
            1,
        )

    def test_default_quantity_is_one_and_uncraftable_item_fails(self):
        self.assertEqual(self.run_script(craft_items, ["wooden_staff"]), 0)
        self.assertEqual(self.api.inventory, {"wooden_staff": 1})

        self.api = type(self.api)()
        self.assertEqual(self.run_script(craft_items, ["copper_ore"]), 1)
        self.assertEqual(self.api.crafted, {})

    def test_configuration_and_unexpected_setup_errors_return_failure(self):
        with patch.object(settings, "validate", side_effect=ValueError("bad config")):
            self.assertEqual(self.run_script(craft_items, ["wooden_staff"]), 1)
        with patch.object(
            craft_items,
            "build_services",
            side_effect=RuntimeError("service setup failed"),
        ):
            self.assertEqual(self.run_script(craft_items, ["wooden_staff"]), 1)

    def test_running_file_as_cli_exits_with_failure_on_invalid_configuration(self):
        self.run_as_entrypoint_without_configuration(craft_items)


if __name__ == "__main__":
    import unittest

    unittest.main()
