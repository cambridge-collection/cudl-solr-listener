# Instructions

## Prerequisites


The following containers needs to be running:

* https://github.com/cambridge-collection/cudl-solr
* https://github.com/cambridge-collection/cudl-search

## Local Build

    docker compose up --force-recreate --build

## Submitting a test notification for a modified json solr file

    curl -X POST -H 'Content-Type: application/json' 'http://localhost:9000/2015-03-31/functions/function/invocations' --data-binary "@./sample/sns-solr-json-modified.json"

**NB:** This test requires that the json source document exists on `AWS_DIST_BUCKET`.
