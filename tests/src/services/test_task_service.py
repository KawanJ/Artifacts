import unittest

from scripts.bootstrap import build_services
from tests.fake_game_api import FakeGameAPI


class TaskServiceTests(unittest.TestCase):
    def test_raw_resource_task_batches_at_capacity_and_banks_task_coins(self):
        api = FakeGameAPI(max_inventory_slots=3)
        api.task_offer.update({"code": "copper_ore", "total": 7})
        api.task_offer["rewards"] = {
            "gold": 150,
            "items": [{"code": "tasks_coin", "quantity": 2}],
        }
        tasks = build_services(api, "tester", (), 0).tasks

        self.assertTrue(tasks.run_item_task())

        self.assertEqual(api.gathered, {"copper_ore": 7})
        self.assertEqual(api.completed_tasks, 1)
        self.assertEqual(api.accepted_tasks, 1)
        self.assertEqual(api.bank.get("tasks_coin"), 2)
        self.assertEqual(api.character["gold"], 150)
        self.assertEqual(api.inventory, {})

    def test_craft_task_gathers_and_trades_in_capacity_safe_batches(self):
        api = FakeGameAPI(max_inventory_slots=12)
        api.task_offer.update({"code": "copper_bar", "total": 3})
        api.items["copper_bar"] = {
            "code": "copper_bar",
            "type": "material",
            "craft": {
                "skill": "mining",
                "items": [{"code": "copper_ore", "quantity": 10}],
                "quantity": 1,
            },
        }
        tasks = build_services(api, "tester", (), 0).tasks

        self.assertTrue(tasks.run_item_task())

        self.assertEqual(api.gathered, {"copper_ore": 30})
        self.assertEqual(api.crafted, {"copper_bar": 3})
        self.assertEqual(api.completed_tasks, 1)
        self.assertEqual(api.inventory, {})

    def test_nested_craft_task_plans_capacity_from_base_ingredients(self):
        api = FakeGameAPI(max_inventory_slots=12)
        api.task_offer.update({"code": "iron_sword", "total": 2})
        api.items["copper_bar"] = {
            "code": "copper_bar",
            "type": "material",
            "craft": {
                "skill": "mining",
                "items": [{"code": "copper_ore", "quantity": 10}],
                "quantity": 1,
            },
        }
        api.items["iron_sword"] = {
            "code": "iron_sword",
            "type": "weapon",
            "craft": {
                "skill": "weaponcrafting",
                "items": [{"code": "copper_bar", "quantity": 1}],
                "quantity": 1,
            },
        }
        tasks = build_services(api, "tester", (), 0).tasks

        self.assertTrue(tasks.run_item_task())

        self.assertEqual(api.gathered, {"copper_ore": 20})
        self.assertEqual(api.crafted, {"copper_bar": 2, "iron_sword": 2})
        self.assertEqual(api.completed_tasks, 1)
        self.assertEqual(api.inventory, {})

    def test_existing_item_task_is_resumed(self):
        api = FakeGameAPI()
        api.character.update(
            {
                "task": "copper_ore",
                "task_type": "items",
                "task_progress": 2,
                "task_total": 5,
            }
        )
        tasks = build_services(api, "tester", (), 0).tasks

        self.assertTrue(tasks.run_item_task())

        self.assertEqual(api.accepted_tasks, 0)
        self.assertEqual(api.gathered, {"copper_ore": 3})
        self.assertEqual(api.completed_tasks, 1)
        self.assertEqual(api.inventory, {})

    def test_task_trade_failure_does_not_complete_task(self):
        api = FakeGameAPI()
        api.task_offer.update({"code": "copper_ore", "total": 1})
        api.fail_actions.add("task/trade")
        tasks = build_services(api, "tester", (), 0).tasks

        self.assertFalse(tasks.run_item_task())

        self.assertEqual(api.completed_tasks, 0)
        self.assertEqual(api.inventory, {"copper_ore": 1})


if __name__ == "__main__":
    unittest.main()
