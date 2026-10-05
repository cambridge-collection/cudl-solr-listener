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
    def test_service_unavailable_is_retryable(self):
        self.assertTrue(app.is_retryable(503))

    def test_service_unavailable_is_marked_for_invocation_failure(self):
        failures = []

        app.record_outcome("item.json", 503, failures)

        self.assertEqual(failures, ["item.json"])

    def test_service_unavailable_fails_the_lambda_invocation(self):
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
            patch.object(app, "submit_request", return_value=503),
            patch.object(app.os, "remove"),
        ):
            with self.assertRaises(RuntimeError):
                app.lambda_handler(event, None)

    def test_permanent_client_error_is_not_retryable(self):
        failures = []

        app.record_outcome("item.json", 400, failures)

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
