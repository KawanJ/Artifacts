import unittest

from src.services.items.item_catalog_service import ItemCatalogService
from tests.fake_game_api import FakeGameAPI


class ItemCatalogServiceTests(unittest.TestCase):
    def test_returns_catalog_metadata_for_the_requested_item(self):
        api = FakeGameAPI()
        service = ItemCatalogService(api)

        self.assertEqual(
            service.get_item("wooden_staff"),
            api.items["wooden_staff"],
        )

    def test_missing_catalog_entry_is_returned_as_missing(self):
        api = FakeGameAPI()
        api.items["missing_item"] = None

        self.assertIsNone(ItemCatalogService(api).get_item("missing_item"))


if __name__ == "__main__":
    unittest.main()
