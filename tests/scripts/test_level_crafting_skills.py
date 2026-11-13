from unittest.mock import patch

from scripts import level_crafting_skills
from tests.script_test_support import ScriptTestCase
from src.config.settings import settings


class LevelCraftingSkillsScriptTests(ScriptTestCase):
    def test_script_recycles_until_skill_level_increases(self):
        result = self.run_script(
            level_crafting_skills,
            ["weaponcrafting", "wooden_staff"],
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.api.character["weaponcrafting_level"], 1)
        self.assertNotIn("wooden_staff", self.api.inventory)
        self.assertEqual(self.api.gathered, {"copper_ore": 1})

    def test_missing_arguments_and_failed_crafting_stop_the_script(self):
        self.assertEqual(self.run_script(level_crafting_skills, []), 1)
        self.assertEqual(
            self.run_script(
                level_crafting_skills,
                ["weaponcrafting", "copper_ore"],
            ),
            1,
        )
        self.assertEqual(self.api.crafted, {})

    def test_script_repeats_a_successful_cycle_until_skill_actually_advances(self):
        self.api = type(self.api)(recycles_without_skill_gain=1)

        result = self.run_script(
            level_crafting_skills,
            ["weaponcrafting", "wooden_staff"],
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.api.recycled, {"wooden_staff": 2})
        self.assertEqual(self.api.character["weaponcrafting_level"], 1)

    def test_recycling_failure_stops_and_configuration_errors_are_reported(self):
        self.api.fail_actions.add("recycling")
        self.assertEqual(
            self.run_script(
                level_crafting_skills,
                ["weaponcrafting", "wooden_staff"],
            ),
            1,
        )
        self.assertEqual(self.api.character["weaponcrafting_level"], 0)

        with patch.object(settings, "validate", side_effect=ValueError("bad config")):
            self.assertEqual(
                self.run_script(
                    level_crafting_skills,
                    ["weaponcrafting", "wooden_staff"],
                ),
                1,
            )
        with patch.object(
            level_crafting_skills,
            "build_services",
            side_effect=RuntimeError("service setup failed"),
        ):
            self.assertEqual(
                self.run_script(
                    level_crafting_skills,
                    ["weaponcrafting", "wooden_staff"],
                ),
                1,
            )

    def test_running_file_as_cli_exits_with_failure_on_invalid_configuration(self):
        self.run_as_entrypoint_without_configuration(level_crafting_skills)


if __name__ == "__main__":
    import unittest

    unittest.main()
