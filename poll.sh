#!/bin/bash
# Layer 1b — poll a live URL until the expected BUILD_ID sentinel appears.
# Usage: ./poll.sh <url> <build_id> [max_attempts]
#
# A green build is not a correct deploy.
# CDN caching means the platform can report success while users still see
# the old version. This script waits for the real evidence.

set -euo pipefail

URL="${1:?Usage: $0 <url> <build_id> [max_attempts]}"
BUILD_ID="${2:?provide BUILD_ID}"
MAX="${3:-30}"
INTERVAL=5

echo "Polling ${URL} for sentinel: ${BUILD_ID}"
echo "Max ${MAX} attempts × ${INTERVAL}s = $((MAX * INTERVAL))s timeout"

for attempt in $(seq 1 "$MAX"); do
    BODY=$(curl -sf --max-time 5 "$URL" 2>/dev/null || true)
    if echo "$BODY" | grep -qF "$BUILD_ID"; then
        echo "✓ Sentinel found on attempt ${attempt}. Deploy verified."
        exit 0
    fi
    ETAG=$(curl -sI --max-time 5 "$URL" 2>/dev/null | grep -i etag | tr -d '\r' || true)
    echo "  [${attempt}/${MAX}] not yet (ETag: ${ETAG:-unknown}) — sleeping ${INTERVAL}s"
    sleep "$INTERVAL"
done

echo "✗ Sentinel not found after ${MAX} attempts. CDN may still be propagating."
exit 1
