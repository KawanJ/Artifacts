from unittest.mock import patch

from scripts import gather_resources
from tests.script_test_support import ScriptTestCase
from src.config.settings import settings


class GatherResourcesScriptTests(ScriptTestCase):
    def test_script_gathers_requested_quantity_and_banks_output(self):
        result = self.run_script(gather_resources, ["copper_ore", "3"])

        self.assertEqual(result, 0)
        self.assertEqual(self.api.gathered, {"copper_ore": 3})
        self.assertEqual(self.api.bank, {"copper_ore": 3})
        self.assertEqual(self.api.inventory, {})

    def test_character_argument_overrides_configured_character(self):
        with patch.object(
            gather_resources,
            "build_services",
            wraps=gather_resources.build_services,
        ) as build_services:
            result = self.run_script(
                gather_resources,
                ["copper_ore", "1", "--character", "SelectedCharacter"],
            )

        self.assertEqual(result, 0)
        self.assertEqual(build_services.call_args.args[1], "SelectedCharacter")

    def test_missing_or_nonpositive_quantity_is_rejected(self):
        self.assertEqual(self.run_script(gather_resources, ["copper_ore"]), 1)
        self.assertEqual(
            self.run_script(gather_resources, ["copper_ore", "0"]),
            1,
        )

    def test_service_failure_produces_a_nonzero_exit_status(self):
        self.assertEqual(
            self.run_script(gather_resources, ["missing_resource", "1"]),
            1,
        )
        self.assertEqual(self.api.gathered, {})

    def test_configuration_and_unexpected_setup_errors_return_failure(self):
        with patch.object(settings, "validate", side_effect=ValueError("bad config")):
            self.assertEqual(
                self.run_script(gather_resources, ["copper_ore", "1"]),
                1,
            )
        with patch.object(
            gather_resources,
            "build_services",
            side_effect=RuntimeError("service setup failed"),
        ):
            self.assertEqual(
                self.run_script(gather_resources, ["copper_ore", "1"]),
                1,
            )

    def test_running_file_as_cli_exits_with_failure_on_invalid_configuration(self):
        self.run_as_entrypoint_without_configuration(gather_resources)


if __name__ == "__main__":
    import unittest

    unittest.main()
