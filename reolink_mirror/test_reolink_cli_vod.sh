#!/bin/sh
set -eu

CLI="${REOLINK_CLI:-$HOME/.local/bin/reolink-cli}"
GATEWAY="${REOLINK_GATEWAY:-$HOME/.local/bin/reolink-gateway}"
NVR_HOST="${NVR_HOST:-192.168.4.201:9000}"
NVR_USER="${NVR_USER:-admin}"
CHANNELS="${CHANNELS:-0 1}"
SINCE="${SINCE:-4h}"
GATEWAY_ADDR="${GATEWAY_ADDR:-127.0.0.1:9000}"
OUTPUT_DIR="${OUTPUT_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/reolink-vod.XXXXXX")}"

if [ -z "${REOLINK_PASSWORD:-}" ]; then
    printf '%s\n' 'REOLINK_PASSWORD must be set; refusing to put a password in argv.' >&2
    exit 2
fi

for binary in "$CLI" "$GATEWAY"; do
    if [ ! -x "$binary" ]; then
        printf 'Executable not found: %s\n' "$binary" >&2
        exit 2
    fi
done

cleanup() {
    if [ -n "${GATEWAY_PID:-}" ]; then
        kill "$GATEWAY_PID" 2>/dev/null || true
        wait "$GATEWAY_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

mkdir -p "$OUTPUT_DIR"

printf 'CLI:       %s\n' "$CLI"
printf 'Gateway:   %s\n' "$GATEWAY"
printf 'NVR:       %s\n' "$NVR_HOST"
printf 'Channels:  %s\n' "$CHANNELS"
printf 'Search:    last %s\n' "$SINCE"
printf 'Output:    %s\n\n' "$OUTPUT_DIR"

"$CLI" --version

printf '\nStarting gateway at %s...\n' "$GATEWAY_ADDR"
"$GATEWAY" --addr "$GATEWAY_ADDR" >"$OUTPUT_DIR/gateway.log" 2>&1 &
GATEWAY_PID=$!

# Give the gateway a moment to bind, then verify its health endpoint.
i=0
while ! curl -fsS "http://${GATEWAY_ADDR}/api/health" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 20 ]; then
        printf 'Gateway did not become healthy. Log:\n' >&2
        cat "$OUTPUT_DIR/gateway.log" >&2 || true
        exit 1
    fi
    sleep 1
done
printf 'Gateway is healthy.\n'

for channel in $CHANNELS; do
    SEARCH_JSON="$OUTPUT_DIR/search-channel-${channel}.json"

    printf '\n=== Channel %s: login and info ===\n' "$channel"
    "$CLI" \
        --gateway-addr "$GATEWAY_ADDR" \
        --host "$NVR_HOST" \
        --user "$NVR_USER" \
        --channel "$channel" \
        login
    "$CLI" \
        --gateway-addr "$GATEWAY_ADDR" \
        --host "$NVR_HOST" \
        --user "$NVR_USER" \
        --channel "$channel" \
        info

    # Do not filter by type here. NVR results may report recordType=none even
    # for an event clip, which would hide a valid person/vehicle recording.
    printf '\nSearching channel %s (all recording types)...\n' "$channel"
    "$CLI" \
        --gateway-addr "$GATEWAY_ADDR" \
        --host "$NVR_HOST" \
        --user "$NVR_USER" \
        --channel "$channel" \
        vod search \
        --since "$SINCE" \
        --stream sub \
        --limit 10 >"$SEARCH_JSON"
    cat "$SEARCH_JSON"

    NAME=$(
        python3 - "$SEARCH_JSON" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if not payload.get("ok"):
    raise SystemExit("VOD search returned an error")
items = (payload.get("data") or {}).get("items") or []
if not items:
    raise SystemExit("No matching recordings found")
# Search results are normally chronological; choose the newest item.
print(items[-1]["name"])
PY
    )

    printf '\nSelected channel %s recording: %s\n' "$channel" "$NAME"
    OUTPUT_FILE="$OUTPUT_DIR/channel-${channel}-${NAME}.mp4"

    printf 'Downloading to: %s\n' "$OUTPUT_FILE"
    "$CLI" \
        --gateway-addr "$GATEWAY_ADDR" \
        --host "$NVR_HOST" \
        --user "$NVR_USER" \
        --channel "$channel" \
        vod download "$NAME" \
        --file "$OUTPUT_FILE"

    if [ ! -s "$OUTPUT_FILE" ]; then
        printf 'Download command succeeded but output is empty: %s\n' "$OUTPUT_FILE" >&2
        exit 1
    fi

    printf '\nDownload succeeded:\n'
    ls -lh "$OUTPUT_FILE"
done

printf 'Output directory: %s\n' "$OUTPUT_DIR"
