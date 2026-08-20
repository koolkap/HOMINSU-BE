#!/usr/bin/env bash
set -Eeuo pipefail

# Start the Hominsu media dependencies and verify that SRS owns RTMP 1935.
# Run from any location inside the repository; Docker Compose is required.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_DIR}/docker-compose.local.yml"
LAN_HOST_IP=""

die() {
    echo "ERROR: $*" >&2
    exit 1
}

if [[ ! -f "$COMPOSE_FILE" ]]; then
    die "docker-compose.local.yml was not found at $COMPOSE_FILE"
fi

if command -v docker >/dev/null 2>&1; then
    DOCKER=(docker)
elif command -v docker.exe >/dev/null 2>&1; then
    # Useful when this script is run in WSL with Docker Desktop installed.
    DOCKER=(docker.exe)
else
    die "Docker CLI is unavailable. Install/start Docker Desktop with WSL integration, or install Docker Engine on Ubuntu."
fi

if ! "${DOCKER[@]}" compose version >/dev/null 2>&1; then
    die "Docker Compose is unavailable. Enable Docker Desktop WSL integration or install the Docker Compose plugin."
fi

if [[ -f "${REPO_DIR}/.env" ]]; then
    LAN_HOST_IP="$(awk -F= '$1 == "LAN_HOST_IP" {print $2; exit}' "${REPO_DIR}/.env" | tr -d '\r')"
fi
if [[ -z "$LAN_HOST_IP" ]]; then
    LAN_HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
LAN_HOST_IP="${LAN_HOST_IP:-127.0.0.1}"

cd "$REPO_DIR"

echo "Starting PostgreSQL and SRS..."
"${DOCKER[@]}" compose -f "$COMPOSE_FILE" up -d postgres srs

for attempt in {1..30}; do
    running="$("${DOCKER[@]}" inspect -f '{{.State.Running}}' hominsu-srs 2>/dev/null || true)"
    if [[ "$running" == "true" ]]; then
        break
    fi
    if (( attempt == 30 )); then
        echo "SRS did not become running. Recent logs:" >&2
        "${DOCKER[@]}" compose -f "$COMPOSE_FILE" logs --tail=100 srs >&2 || true
        exit 1
    fi
    sleep 1
done

echo
"${DOCKER[@]}" compose -f "$COMPOSE_FILE" ps
echo
echo "Published SRS ports:"
"${DOCKER[@]}" port hominsu-srs || true

if ! "${DOCKER[@]}" port hominsu-srs 1935/tcp 2>/dev/null | grep -q .; then
    echo "ERROR: hominsu-srs is running but RTMP 1935 is not published." >&2
    "${DOCKER[@]}" compose -f "$COMPOSE_FILE" logs --tail=100 srs >&2 || true
    exit 1
fi

if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 5 http://127.0.0.1:1985/api/v1/versions >/dev/null; then
        echo "SRS HTTP API:             OK"
    else
        echo "WARNING: SRS HTTP API 1985 is not responding yet."
    fi
fi

echo
echo "SRS is running."
echo "Insta360 RTMP URL:        rtmp://${LAN_HOST_IP}:1935/live/insta-001"
echo "Direct HLS URL:           http://${LAN_HOST_IP}:8080/live/insta-001.m3u8"
echo
echo "Verify from Windows PowerShell:"
echo "  Test-NetConnection ${LAN_HOST_IP} -Port 1935"
echo
echo "Expected: TcpTestSucceeded : True"

