# Cudl Solr Listener

The Cudl Solr Listener is a component in the Cambridge Digital Collection Platform. It runs as an AWS Lambda function that processes SNS notifications triggered by the creation or deletion of JSON files used by Solr.

It listens for two event types:
- **ObjectCreated:** Downloads the JSON file from S3, validates it, and submits it via a PUT request.
- **ObjectRemoved:** Deletes the corresponding record via a DELETE request based on the filename.

## Prerequisites

Before running the project locally, ensure that the following containers are running:

- [cudl-solr](https://github.com/cambridge-collection/cudl-solr)
- [cudl-search](https://github.com/cambridge-collection/cudl-search)

## Environment Variables

The Lambda function requires the following environment variables to be set:

- `API_HOST`: The API host for submitting requests.
- `API_PORT`: The port number of the API (optional).
- `API_PATH`: The API path for the submission endpoint.
- `RELEASES_PARTITIONED`: When set to `true`, DELETE requests include an `isReleased` query parameter derived from the object's root directory (`unreleased/...` → `false`, otherwise `true`). Optional; defaults to off.

## Local Build and Run

Before building, log in to the relevant AWS account and ensure that your credentials are correctly set in your environment.

To build and run the project locally using Docker Compose, run:

```bash
docker compose up --force-recreate --build
```
