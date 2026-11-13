import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests

from src.client.api_client import APIClient, APIError


class APIClientTests(unittest.TestCase):
    def setUp(self):
        self.client = APIClient(
            "secret-for-test",
            base_url="https://example.test/",
            max_retries=0,
            timeout=7,
        )

    def tearDown(self):
        self.client.close()

    def test_http_methods_send_expected_urls_payloads_and_parameters(self):
        response = Mock()
        response.text = '{"ok": true}'
        response.json.return_value = {"ok": True}

        with patch.object(
            self.client.session,
            "request",
            return_value=response,
        ) as request:
            self.assertEqual(
                self.client.get("/characters", params={"page": 2}),
                {"ok": True},
            )
            self.assertEqual(
                self.client.post("/action", data={"code": "ore"}),
                {"ok": True},
            )
            self.assertEqual(
                self.client.put("/settings", data={"enabled": True}),
                {"ok": True},
            )
            self.assertEqual(self.client.delete("/settings"), {"ok": True})

        self.assertEqual(
            [entry.kwargs["method"] for entry in request.call_args_list],
            ["GET", "POST", "PUT", "DELETE"],
        )
        self.assertEqual(
            request.call_args_list[0].kwargs,
            {
                "method": "GET",
                "url": "https://example.test/characters",
                "json": None,
                "params": {"page": 2},
                "timeout": 7,
            },
        )
        self.assertEqual(
            request.call_args_list[1].kwargs["json"],
            {"code": "ore"},
        )

    def test_empty_success_response_returns_empty_object(self):
        response = Mock()
        response.text = ""

        with patch.object(self.client.session, "request", return_value=response):
            self.assertEqual(self.client.get("/empty"), {})

    def test_http_error_preserves_status_and_response_details(self):
        response = Mock()
        response.text = "unauthorized"
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=SimpleNamespace(status_code=401, text="unauthorized")
        )

        with patch.object(self.client.session, "request", return_value=response):
            with self.assertRaises(APIError) as raised:
                self.client.get("/private")

        self.assertEqual(raised.exception.status_code, 401)
        self.assertIn("HTTP 401: unauthorized", str(raised.exception))

    def test_request_error_is_wrapped_without_a_status_code(self):
        with patch.object(
            self.client.session,
            "request",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            with self.assertRaises(APIError) as raised:
                self.client.get("/slow")

        self.assertIsNone(raised.exception.status_code)
        self.assertIn("Request failed: timed out", str(raised.exception))

    def test_client_sets_auth_headers_and_context_exit_closes_session(self):
        self.assertEqual(
            self.client.session.headers["Authorization"],
            "Bearer secret-for-test",
        )
        with patch.object(self.client, "close") as close:
            with self.client:
                pass
        close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
