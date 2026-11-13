import unittest

from src.domain.world import (
    get_crafting_location,
    get_monster_location,
    get_resource_location,
)


class WorldLocationTests(unittest.TestCase):
    def test_known_resource_monster_and_crafting_locations(self):
        self.assertEqual(get_resource_location("copper_ore"), (2, 0))
        self.assertEqual(get_monster_location("chicken"), (0, 1))
        self.assertEqual(get_crafting_location("cooking"), (1, 1))

    def test_unknown_resource_monster_and_skill_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown resource 'missing_ore'"):
            get_resource_location("missing_ore")
        with self.assertRaisesRegex(ValueError, "Unknown monster 'missing_monster'"):
            get_monster_location("missing_monster")
        with self.assertRaisesRegex(ValueError, "Unknown crafting skill 'missing_skill'"):
            get_crafting_location("missing_skill")


if __name__ == "__main__":
    unittest.main()
