import unittest

from scripts.bootstrap import build_services
from tests.fake_game_api import FakeGameAPI


class NoCooldownRestAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/rest"):
            response["data"].pop("cooldown", None)
        return response


class CombatRecoveryServiceTests(unittest.TestCase):
    def test_uses_smallest_non_overflowing_food_then_rests_for_remainder(self):
        api = FakeGameAPI(
            inventory={"cooked_shrimp": 1, "small_food": 2},
            hp=85,
        )
        api.items["small_food"] = {
            "code": "small_food",
            "type": "consumable",
            "effects": [{"code": "heal", "value": 5}],
        }
        services = build_services(
            api,
            "tester",
            ("cooked_shrimp", "small_food"),
            0,
        )
        services.combat.food_service.prepare_food()

        self.assertTrue(services.combat.recovery_service.recover_to_hp(100))

        self.assertEqual(api.character["hp"], 100)
        self.assertEqual(api.inventory, {"cooked_shrimp": 1})
        self.assertEqual(
            services.combat.food_service.used_quantities,
            {"small_food": 2},
        )

    def test_failed_food_use_falls_back_to_rest(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 1}, hp=80)
        api.fail_actions.add("use")
        services = build_services(api, "tester", ("cooked_shrimp",), 0)
        services.combat.food_service.prepare_food()

        self.assertTrue(services.combat.recovery_service.recover_to_hp(90))

        self.assertEqual(api.character["hp"], 100)
        self.assertEqual(api.inventory, {"cooked_shrimp": 1})

    def test_recovery_fails_if_rest_does_not_increase_hp(self):
        api = FakeGameAPI(hp=20, rest_heals=False)
        services = build_services(api, "tester", (), 0)
        services.combat.food_service.prepare_food()

        self.assertFalse(services.combat.recovery_service.recover_to_hp(80))
        self.assertEqual(api.character["hp"], 20)

    def test_rest_api_failure_is_not_reported_as_success(self):
        api = FakeGameAPI()
        api.fail_actions.add("rest")
        recovery = build_services(api, "tester", (), 0).combat.recovery_service

        self.assertFalse(recovery.rest())
        self.assertEqual(api.character["hp"], 100)

    def test_recover_to_hp_stops_if_rest_action_fails(self):
        api = FakeGameAPI(hp=20)
        api.fail_actions.add("rest")
        services = build_services(api, "tester", (), 0)
        services.combat.food_service.prepare_food()

        self.assertFalse(services.combat.recovery_service.recover_to_hp(80))
        self.assertEqual(api.character["hp"], 20)

    def test_recovery_replenishes_food_without_re_equip_when_no_monster_is_given(self):
        api = FakeGameAPI(hp=80)
        api.bank["cooked_shrimp"] = 1
        services = build_services(api, "tester", ("cooked_shrimp",), 1)
        self.assertTrue(services.combat.food_service.prepare_food())

        self.assertTrue(services.combat.recovery_service.recover_to_hp(91))

        self.assertEqual(api.character["hp"], 100)
        self.assertEqual(api.gathered, {"shrimp": 1})
        self.assertEqual(api.inventory, {})

    def test_rest_succeeds_when_response_omits_cooldown(self):
        api = NoCooldownRestAPI(hp=40)

        self.assertTrue(
            build_services(api, "tester", (), 0).combat.recovery_service.rest()
        )
        self.assertEqual(api.character["hp"], 100)

    def test_skips_actions_when_hp_already_meets_threshold(self):
        api = FakeGameAPI(hp=50)
        services = build_services(api, "tester", (), 0)
        services.combat.food_service.prepare_food()

        self.assertTrue(services.combat.recovery_service.recover_to_hp(40))
        self.assertEqual(api.character["hp"], 50)
        self.assertEqual(api.inventory, {})


if __name__ == "__main__":
    unittest.main()
