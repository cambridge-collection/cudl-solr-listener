#! /bin/sh

function handler () {
   JSON_FILE=$(echo "$1" | jq -r '.Records[].body'| jq -r '.Records[].s3.object.key') 1>&2

   echo "Indexing ${JSON_FILE}" 1>&2
   aws s3 cp --quiet s3://${AWS_DIST_BUCKET}/${JSON_FILE} /tmp/opt/cdcp/solr-json 1>&2 \
    && echo "File downloaded" 1>&2

   # Test that json is plausibly valid before submitting
   if $(jq empty /tmp/opt/cdcp/${JSON_FILE} &>/dev/null);
      then
        echo "Submitting file" 1>&2
        echo '{"http-code":' $(curl -s -o /dev/null -w "%{http_code}" -X PUT -H 'accept: application/json' "http://${API_HOST}:${API_PORT}/item" --data-binary "@/tmp/opt/cdcp/${JSON_FILE}") '}' 1>&2
      else
        echo "ERROR: File not submitted for reindexing because it doesn't seem valid" 1>&2;
      fi
    }
