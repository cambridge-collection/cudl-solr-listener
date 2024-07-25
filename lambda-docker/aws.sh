#! /bin/sh

function handler() {
	set -a
	# Set defaults for env vars that are unlikely to change.
	: "${API_PORT:=}"
	set +a

	echo "Parsing event notification" 1>&2
	echo "$1" 1>&2

	EVENTNAME=$(echo "$1" | jq -r '.Records[].body' | jq -r '.Records[].eventName') 1>&2
	S3_BUCKET=$(echo "$1" | jq -r '.Records[].body' | jq -r '.Records[].s3.bucket.name') 1>&2
	JSON_FILE=$(echo "$1" | jq -r '.Records[].body' | jq -r '.Records[].s3.object.key') 1>&2

	if [[ "$EVENTNAME" =~ ^ObjectCreated ]]; then
		API_METHOD="PUT"
	elif [[ "$EVENTNAME" =~ ^ObjectRemoved ]]; then
		API_METHOD="DELETE"
	else
		API_METHOD="UNSUPPORTED"
	fi

	if [[ -v "API_HOST" && -v "API_PATH" && -n "$S3_BUCKET" && -n "$JSON_FILE" && -n "$EVENTNAME" ]]; then
		if [[ "$EVENTNAME" =~ ^ObjectCreated ]]; then
			API_METHOD="PUT"
			echo "Indexing ${JSON_FILE}" 1>&2
			echo "Attempting to download s3://${S3_BUCKET}/${JSON_FILE}" 1>&2
			aws s3 cp --quiet s3://${S3_BUCKET}/${JSON_FILE} /tmp/opt/cdcp/${JSON_FILE} 1>&2 &&
				echo "File downloaded" 1>&2

			echo "Testing file is plausibly valid JSON" 1>&2
			# Test that json is plausibly valid before submitting
			if $(jq empty /tmp/opt/cdcp/${JSON_FILE} &>/dev/null); then
				echo "File OK" 1>&2
				if [ -z "${API_PORT}" ]; then
					HOSTNAME=${API_HOST}
				else
					HOSTNAME=${API_HOST}:${API_PORT}
				fi
				echo "Submitting file via ${API_METHOD} to http://${HOSTNAME}/${API_PATH}" 1>&2
				response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 120 -X $API_METHOD -H 'accept: application/json' "http://${HOSTNAME}/${API_PATH}" --data-binary "@/tmp/opt/cdcp/${JSON_FILE}")
				msg='{"http-code": '$response_code' }'
				if ! [[ $response_code =~ ^2[0-9][0-9] ]]; then
					echo "ERROR: ${msg}" 1>&2
					return 1
				else
					echo $msg 1>&2
				fi
			else
				echo "ERROR: File not submitted for reindexing because it doesn't seem valid" 1>&2
				return 1
			fi
		elif [[ "$EVENTNAME" =~ ^ObjectRemoved ]]; then
			API_METHOD="DELETE"
			ID_VAL=$(basename $(basename $JSON_FILE ".json") ".collection")
			if [[ -n $ID_VAL ]]; then
				echo "Deleting ${JSON_FILE} using ID \"${ID_VAL}\"" 1>&2
				echo "Submitting request via ${API_METHOD}" 1>&2
				response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 120 -X $API_METHOD "http://${API_HOST}:${API_PORT}/${API_PATH}/${ID_VAL}")
				msg='{"http-code": '$response_code' }'
				if ! [[ $response_code =~ ^2[0-9][0-9] ]]; then
					echo "ERROR: ${msg}" 1>&2
					return 1
				else
					echo $msg 1>&2
				fi
			fi
		else
			echo "ERROR: Unsupported event: ${EVENTNAME}" 1>&2
			return 1
		fi
	else
		if [[ ! -v "API_HOST" ]]; then echo "ERROR: API_HOST environment var not set" 1>&2; fi
		if [[ ! -v "API_PORT" ]]; then echo "ERROR: API_PORT environment var not set" 1>&2; fi
		if [[ ! -v "API_PATH" ]]; then echo "ERROR: API_PATH environment var not set" 1>&2; fi
		if [[ -z "$S3_BUCKET" ]]; then echo "ERROR: Problem parsing event json for S3 Bucket" 1>&2; fi
		if [[ -z "$JSON_FILE" ]]; then echo "ERROR: Problem parsing event json for JSON filename" 1>&2; fi
		if [[ -z "$EVENTNAME" ]]; then echo "ERROR: Problem parsing event json for eventName" 1>&2; fi
		if [[ ! -v "API_METHOD" ]]; then echo "ERROR: Problem parsing event json to determine API_METHOD for $EVENTNAME" 1>&2; fi
		return 1
	fi
}
