#!/usr/bin/env bash
# POST a single ingest payload to INGEST_URL (Edge Function or Supabase REST).
# Does not call HubSpot. Requires INGEST_URL and INGEST_BEARER in the environment.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: INGEST_URL=... INGEST_BEARER=... $0 <payload.json>" >&2
  exit 1
fi

PAYLOAD_FILE="$1"

if [[ -z "${INGEST_URL:-}" ]]; then
  echo "Set INGEST_URL (e.g. https://<ref>.supabase.co/functions/v1/signal-ingest)" >&2
  exit 1
fi

if [[ -z "${INGEST_BEARER:-}" ]]; then
  echo "Set INGEST_BEARER (service role or function secret — never commit)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/validate_payload.py" "$PAYLOAD_FILE"

HTTP_CODE=$(curl -sS -o /tmp/signal_ingest_response.json -w "%{http_code}" \
  -X POST "$INGEST_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${INGEST_BEARER}" \
  --data-binary "@${PAYLOAD_FILE}")

echo "HTTP ${HTTP_CODE}"
cat /tmp/signal_ingest_response.json
echo ""

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  exit 1
fi
