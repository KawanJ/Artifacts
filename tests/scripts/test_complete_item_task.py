from types import SimpleNamespace
from unittest.mock import patch

from scripts import complete_item_task
from tests.script_test_support import ScriptTestCase
from src.config.settings import settings


class CompleteItemTaskScriptTests(ScriptTestCase):
    def test_script_accepts_and_completes_an_item_task(self):
        self.assertEqual(self.run_script(complete_item_task, []), 0)

        self.assertEqual(self.api.accepted_tasks, 1)
        self.assertEqual(self.api.completed_tasks, 1)
        self.assertEqual(self.api.bank.get("tasks_coin"), 2)

    def test_character_name_input_overrides_configured_character(self):
        with patch.object(
            complete_item_task,
            "build_services",
            wraps=complete_item_task.build_services,
        ) as build_services:
            result = self.run_script(
                complete_item_task,
                [],
                {"ITEM_TASK_CHARACTER_NAME": "AnotherCharacter"},
            )

        self.assertEqual(result, 0)
        self.assertEqual(build_services.call_args.args[1], "AnotherCharacter")

    def test_blank_character_name_uses_configured_character(self):
        with patch.object(
            complete_item_task,
            "build_services",
            wraps=complete_item_task.build_services,
        ) as build_services:
            result = self.run_script(
                complete_item_task,
                [],
                {"ITEM_TASK_CHARACTER_NAME": ""},
            )

        self.assertEqual(result, 0)
        self.assertEqual(build_services.call_args.args[1], "tester")

    def test_configuration_and_service_failures_return_nonzero_status(self):
        with patch.object(settings, "validate", side_effect=ValueError("bad config")):
            self.assertEqual(self.run_script(complete_item_task, []), 1)
        with patch.object(
            complete_item_task,
            "build_services",
            side_effect=RuntimeError("service setup failed"),
        ):
            self.assertEqual(self.run_script(complete_item_task, []), 1)

    def test_task_service_failure_returns_nonzero_status(self):
        services = SimpleNamespace(
            tasks=SimpleNamespace(run_item_task=lambda: False)
        )
        with patch.object(complete_item_task, "build_services", return_value=services):
            self.assertEqual(self.run_script(complete_item_task, []), 1)

    def test_running_file_as_entrypoint_exits_on_invalid_configuration(self):
        self.run_as_entrypoint_without_configuration(complete_item_task)


if __name__ == "__main__":
    import unittest

    unittest.main()
