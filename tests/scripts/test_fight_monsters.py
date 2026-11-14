from unittest.mock import patch

from scripts import fight_monsters
from tests.script_test_support import ScriptTestCase
from src.config.settings import settings


class FightMonstersScriptTests(ScriptTestCase):
    def test_script_runs_fights_and_recovers_character(self):
        self.api.character["hp"] = 40

        result = self.run_script(fight_monsters, ["chicken", "2"])

        self.assertEqual(result, 0)
        self.assertEqual(self.api.fights, [(0, 1), (0, 1)])
        self.assertEqual(self.api.character["hp"], self.api.character["max_hp"])

    def test_character_argument_overrides_configured_character(self):
        with patch.object(
            fight_monsters,
            "build_services",
            wraps=fight_monsters.build_services,
        ) as build_services:
            result = self.run_script(
                fight_monsters,
                ["chicken", "--character", "SelectedCharacter"],
            )

        self.assertEqual(result, 0)
        self.assertEqual(build_services.call_args.args[1], "SelectedCharacter")

    def test_missing_arguments_use_environment_configuration(self):
        result = self.run_script(
            fight_monsters,
            [],
            {"MONSTER_CODE": "chicken", "MONSTER_FIGHT_COUNT": "2"},
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.api.fights), 2)

    def test_environment_aliases_and_default_fight_count_are_respected(self):
        result = self.run_script(
            fight_monsters,
            [],
            {"MONSTER_NAME": "chicken"},
        )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.api.fights), 1)

    def test_missing_monster_and_invalid_environment_count_are_rejected(self):
        empty_environment = {
            "MONSTER_CODE": "",
            "MONSTER_NAME": "",
            "MONSTER_FIGHT_COUNT": "",
            "MONSTER_COUNT": "",
        }
        self.assertEqual(self.run_script(fight_monsters, [], empty_environment), 1)
        self.assertEqual(
            self.run_script(
                fight_monsters,
                [],
                {"MONSTER_CODE": "chicken", "MONSTER_FIGHT_COUNT": "invalid"},
            ),
            1,
        )

    def test_invalid_fight_count_is_rejected(self):
        self.assertEqual(
            self.run_script(fight_monsters, ["chicken", "not-a-number"]),
            1,
        )
        self.assertEqual(self.run_script(fight_monsters, ["chicken", "0"]), 1)
        self.assertEqual(self.api.fights, [])

    def test_combat_failure_is_reported_as_nonzero_exit_status(self):
        self.api.fail_actions.add("fight")

        self.assertEqual(self.run_script(fight_monsters, ["chicken"]), 1)
        self.assertEqual(self.api.fights, [])

    def test_configuration_and_unexpected_setup_errors_return_failure(self):
        with patch.object(settings, "validate", side_effect=ValueError("bad config")):
            self.assertEqual(self.run_script(fight_monsters, ["chicken"]), 1)
        with patch.object(
            fight_monsters,
            "build_services",
            side_effect=RuntimeError("service setup failed"),
        ):
            self.assertEqual(self.run_script(fight_monsters, ["chicken"]), 1)

    def test_running_file_as_cli_exits_with_failure_on_invalid_configuration(self):
        self.run_as_entrypoint_without_configuration(fight_monsters)


if __name__ == "__main__":
    import unittest

    unittest.main()
