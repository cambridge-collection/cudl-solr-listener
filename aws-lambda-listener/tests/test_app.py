import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

LISTENER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, LISTENER_DIR)

with patch.dict(sys.modules, {"boto3": Mock()}):
    import app


class RetryResponseTests(unittest.TestCase):
    def test_success_is_not_a_failure(self):
        failures = []

        app.record_outcome("item.json", 204, failures)

        self.assertEqual(failures, [])

    def test_every_non_2xx_is_a_failure(self):
        for status_code in (307, 400, 404, 503):
            with self.subTest(status_code=status_code):
                failures = []

                app.record_outcome("item.json", status_code, failures)

                self.assertEqual(failures, ["item.json (HTTP %s)" % status_code])

    def test_no_response_is_a_failure(self):
        failures = []

        app.record_outcome("item.json", None, failures)

        self.assertEqual(failures, ["item.json (no response)"])

    def test_redirects_are_not_followed(self):
        with patch.object(app.requests, "delete", return_value=Mock(status_code=307)) as delete:
            status_code = app.submit_request("DELETE", "http://api/item/x", "x.json")

        self.assertEqual(status_code, 307)
        self.assertFalse(delete.call_args.kwargs["allow_redirects"])

    def test_failure_fails_the_lambda_invocation(self):
        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "Records": [
                                {
                                    "eventName": "ObjectCreated:Put",
                                    "s3": {
                                        "bucket": {"name": "bucket"},
                                        "object": {"key": "item.json"},
                                    },
                                }
                            ]
                        }
                    )
                }
            ]
        }

        environment = {
            "API_HOST": "solr-api",
            "API_PORT": "8081",
            "API_PATH": "item",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(app, "download_s3_file"),
            patch.object(app, "validate_json_file", return_value=True),
            patch.object(app, "submit_request", return_value=400),
            patch.object(app.os, "remove"),
        ):
            with self.assertRaisesRegex(RuntimeError, r"item\.json \(HTTP 400\)"):
                app.lambda_handler(event, None)


if __name__ == "__main__":
    unittest.main()
