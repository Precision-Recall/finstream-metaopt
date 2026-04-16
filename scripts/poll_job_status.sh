#!/usr/bin/env bash
# scripts/poll_job_status.sh
#
# Poll /api/job_status?job=<JOB_NAME> until the background job reports
# success or failure, or until the retry limit is reached.
#
# Usage:
#   ./scripts/poll_job_status.sh <BASE_URL> <JOB_NAME>
#
# The BASE_URL is read from the first argument and is never echoed to stdout,
# so it does not appear in CI logs even without log masking.
#
# Exit codes:
#   0 — job completed successfully
#   1 — job failed or timed out

set -euo pipefail

BASE_URL="${1:?BASE_URL is required as \$1}"
JOB_NAME="${2:?JOB_NAME is required as \$2}"

# How long to wait between polls and how many times to retry.
# 20 retries × 15 s = up to 5 minutes of polling.
MAX_RETRIES=20
SLEEP_SECONDS=15

echo "Polling job status for '${JOB_NAME}' (max ${MAX_RETRIES} attempts, ${SLEEP_SECONDS}s apart)..."

attempt=0
while [ "$attempt" -lt "$MAX_RETRIES" ]; do
  attempt=$((attempt + 1))

  # Fetch the job status JSON.  Redirect stderr to /dev/null so curl errors
  # (e.g. network timeouts) don't expose the URL in the process list.
  RESPONSE=$(curl -s --max-time 30 --connect-timeout 10 \
    "${BASE_URL}/api/job_status?job=${JOB_NAME}" 2>/dev/null || true)

  # Extract the "status" field from the JSON response.
  STATUS=$(echo "${RESPONSE}" | grep -o '"status":"[^"]*"' | head -1 | sed 's/"status":"//;s/"//')

  echo "Attempt ${attempt}/${MAX_RETRIES}: job status = '${STATUS}'"

  case "${STATUS}" in
    success|done)
      echo "Job '${JOB_NAME}' completed successfully."
      exit 0
      ;;
    error|failed)
      echo "Job '${JOB_NAME}' reported failure. Response: ${RESPONSE}"
      exit 1
      ;;
    running|pending|accepted|not_started)
      # Job is still in progress; wait before the next poll.
      if [ "$attempt" -lt "$MAX_RETRIES" ]; then
        echo "Job still in progress. Waiting ${SLEEP_SECONDS}s..."
        sleep $SLEEP_SECONDS
      fi
      ;;
    *)
      # Unexpected or empty status — treat as still-running to be resilient
      # to transient network errors.
      echo "Unexpected status '${STATUS}' (full response: ${RESPONSE}). Waiting ${SLEEP_SECONDS}s..."
      if [ "$attempt" -lt "$MAX_RETRIES" ]; then
        sleep $SLEEP_SECONDS
      fi
      ;;
  esac
done

echo "Timed out waiting for job '${JOB_NAME}' after $((MAX_RETRIES * SLEEP_SECONDS)) seconds."
exit 1
