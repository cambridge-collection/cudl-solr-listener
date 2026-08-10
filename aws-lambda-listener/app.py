import os
import json
import re
import urllib.parse
import logging
import boto3
import requests
from typing import Any, Dict, Optional

# Configure logging to standard error.
logger = logging.getLogger()
logger.setLevel(
    logging.getLevelNamesMapping().get(
        os.environ.get("LOG_LEVEL", "ERROR").upper(), logging.ERROR
    )
)

# Compile a regex pattern to match any wildcard characters.
WILDCARD_PATTERN = re.compile(r"[\*\?\{\}\[\]\|]")

s3_client = boto3.client("s3")


def download_s3_file(bucket: str, key: str, dest_path: str) -> None:
    """Download the file from S3 to a local path."""
    logger.info("Attempting to download s3://%s/%s", bucket, key)
    s3_client.download_file(bucket, key, dest_path)
    logger.info("File downloaded to %s", dest_path)


def validate_json_file(filepath: str) -> bool:
    """Validate that the file is valid JSON."""
    try:
        with open(filepath, "r") as f:
            json.load(f)
        return True
    except Exception as e:
        logger.error("File validation failed: %s", e)
        return False


def submit_request(
    method: str, url: str, file_path: Optional[str] = None
) -> Optional[int]:
    """Submit a request to the API endpoint.

    For PUT, file_path is used to send binary data.
    For DELETE, no file is sent.
    """
    logger.info("Submitting file via %s to %s", method, url)
    headers = {"accept": "application/json"}
    try:
        if method == "PUT" and file_path:
            with open(file_path, "rb") as f:
                response = requests.put(url, headers=headers, data=f, timeout=120)
        elif method == "DELETE":
            response = requests.delete(url, timeout=120)
        else:
            logger.error("Unsupported method or missing file for PUT")
            return None
        logger.info("Response code: %s", response.status_code)
        return response.status_code
    except Exception as e:
        logger.error("Error submitting request: %s", e)
        return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.info("Parsing event notification")
    logger.debug(json.dumps(event))

    API_HOST: Optional[str] = os.environ.get("API_HOST")
    API_PORT: Optional[str] = os.environ.get("API_PORT", "")
    API_PATH: Optional[str] = os.environ.get("API_PATH")
    RELEASES_PARTITIONED: bool = (
        os.environ.get("RELEASES_PARTITIONED", "").lower() == "true"
    )

    if not API_HOST:
        logger.error("ERROR: API_HOST environment variable not set")
    if API_PORT == "":
        logger.info(
            "API_PORT not set; proceeding without port for ObjectCreated events"
        )
    if not API_PATH:
        logger.error("ERROR: API_PATH environment variable not set")

    # Process each SNS record.
    for record in event.get("Records", []):
        try:
            sns_body: Dict[str, Any] = json.loads(record.get("body", "{}"))
            inner_records = sns_body.get("Records", [])
        except Exception as e:
            logger.error("Error parsing SNS body: %s", e)
            continue

        for inner in inner_records:
            event_name: str = inner.get("eventName", "")
            s3_info: Dict[str, Any] = inner.get("s3", {})
            s3_bucket: str = s3_info.get("bucket", {}).get("name", "")
            json_file: str = urllib.parse.unquote_plus(
                s3_info.get("object", {}).get("key", "")
            )

            logger.info("Processing event: %s", event_name)
            logger.info("Bucket: %s, Key: %s", s3_bucket, json_file)

            # Check for wildcard characters to avoid catastrophic deletes.
            if WILDCARD_PATTERN.search(json_file) or WILDCARD_PATTERN.search(s3_bucket):
                if WILDCARD_PATTERN.search(json_file):
                    logger.error(
                        "ERROR: File not processed because wildcard character in filename"
                    )
                if WILDCARD_PATTERN.search(s3_bucket):
                    logger.error(
                        "ERROR: File not processed because wildcard character in bucket name"
                    )
                continue

            if not all([API_HOST, API_PATH, s3_bucket, json_file, event_name]):
                if not API_HOST:
                    logger.error("ERROR: API_HOST environment variable not set")
                if API_PORT == "":
                    logger.error("ERROR: API_PORT environment variable not set")
                if not API_PATH:
                    logger.error("ERROR: API_PATH environment variable not set")
                if not s3_bucket:
                    logger.error("ERROR: Problem parsing event json for S3 Bucket")
                if not json_file:
                    logger.error("ERROR: Problem parsing event json for JSON filename")
                if not event_name:
                    logger.error("ERROR: Problem parsing event json for eventName")
                continue

            if event_name.startswith("ObjectCreated"):
                method = "PUT"
            elif event_name.startswith("ObjectRemoved"):
                method = "DELETE"
            else:
                logger.error("ERROR: Unsupported event: %s", event_name)
                continue

            if method == "PUT":
                logger.info("Indexing %s", json_file)

                dest_dir = "/tmp/opt/cdcp"
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, os.path.basename(json_file))

                try:
                    download_s3_file(s3_bucket, json_file, dest_path)
                except Exception as e:
                    logger.error("Error downloading file: %s", e)
                    continue

                logger.info("Testing file is plausibly valid JSON")
                if not validate_json_file(dest_path):
                    logger.error(
                        "ERROR: File not submitted for reindexing because it doesn't seem valid"
                    )
                    continue
                logger.info("File OK")

                hostname = f"{API_HOST}:{API_PORT}" if API_PORT else API_HOST
                url = f"http://{hostname}/{API_PATH}"
                status_code = submit_request(method, url, file_path=dest_path)
                try:
                    os.remove(dest_path)
                    logger.info("Deleted temporary file: %s", dest_path)
                except Exception as e:
                    logger.error("Failed to delete temporary file %s: %s", dest_path, e)
                msg = {"http-code": status_code}
                if not (status_code and 200 <= status_code < 300):
                    logger.error("ERROR: %s", msg)
                else:
                    logger.info(msg)

            elif method == "DELETE":
                # Derive an ID by stripping .json or .collection.json suffixes.
                basename = os.path.basename(json_file)
                id_val = re.sub(r"(\.collection)?\.json$", "", basename)

                if not id_val:
                    logger.error(
                        "ERROR: Could not derive an ID from filename %s", json_file
                    )
                    continue
                logger.info('Deleting %s using ID "%s"', json_file, id_val)

                url = f"http://{API_HOST}:{API_PORT}/{API_PATH}/{id_val}"

                if RELEASES_PARTITIONED:
                    # Released and unreleased items are written to different locations
                    root_dir = json_file.split("/")[0]
                    item_released = root_dir != "unreleased"
                    query = urllib.parse.urlencode(
                        {"isReleased": str(item_released).lower()}
                    )
                    url = f"{url}?{query}"
                    logger.info(
                        "Releases partitioned; isReleased=%s",
                        str(item_released).lower(),
                    )

                status_code = submit_request(method, url)
                msg = {"http-code": status_code}
                if not (status_code and 200 <= status_code < 300):
                    logger.error("ERROR: %s", msg)
                else:
                    logger.info(msg)

    return {"status": "done"}
