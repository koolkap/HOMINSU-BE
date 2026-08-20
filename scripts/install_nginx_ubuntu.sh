#!/usr/bin/env bash
set -Eeuo pipefail

# Install and configure Nginx for the Hominsu Ubuntu host.
#
# Nginx proxies HTTP/WebSocket/HLS traffic. SRS remains the RTMP server on port 1935.
# Run as a normal user with sudo access from the repository root or any clone of it.
#
# Example:
#   bash scripts/install_nginx_ubuntu.sh --ip 192.168.1.25 --configure-ufw
#
# The existing Python helper is used to update .env and generate the LAN URLs. No Python
# third-party packages are required by that helper.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SITE_NAME="hominsu"
SITE_AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}.conf"
SITE_ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}.conf"
NGINX_PORT=8088
APP_PORT=8000
SRS_HTTP_PORT=8080
SRS_RTMP_PORT=1935
FRONTEND_PORT=3000
HOST_IP=""
SERVER_NAME="_"
CONFIGURE_UFW=1
ENABLE_UFW=0
SKIP_ENV=0

usage() {
    cat <<'USAGE'
Usage:
  bash scripts/install_nginx_ubuntu.sh [options]

Options:
  --ip ADDRESS          Override LAN IPv4 address; otherwise read LAN_HOST_IP from .env.
  --server-name NAME   Nginx server_name; default is _ (all hostnames).
  --nginx-port PORT    External HTTP port; default is 8088.
  --frontend-port PORT Frontend dev-server port for CORS; default is 3000.
  --configure-ufw      Legacy alias for enabling UFW rule configuration.
  --no-ufw              Do not install or configure UFW.
  --enable-ufw          Enable UFW after allowing OpenSSH, RTMP, and Nginx.
  --skip-env           Do not update the repository .env file.
  -h, --help           Show this help.

Nginx does not ingest RTMP. SRS continues to receive:
  rtmp://SERVER_IP:1935/live/STREAM_KEY
USAGE
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

valid_port() {
    [[ "$1" =~ ^[0-9]+$ ]] && (( 1 <= 10#$1 && 10#$1 <= 65535 ))
}

valid_ipv4() {
    local value="$1"
    [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    local part
    IFS=. read -r -a parts <<< "$value"
    for part in "${parts[@]}"; do
        (( part >= 0 && part <= 255 )) || return 1
    done
}

detect_host_ip() {
    local detected

    # WSL2 has an internal 172.x address, which is not normally reachable from
    # a phone on Wi-Fi. When available, prefer the Windows host's active adapter.
    if command -v ipconfig.exe >/dev/null 2>&1; then
        detected="$(ipconfig.exe 2>/dev/null | tr -d '\r' | awk '/IPv4 Address/ {print $NF; exit}')"
        if valid_ipv4 "$detected" && [[ "$detected" != 127.* ]]; then
            printf '%s' "$detected"
            return
        fi
    fi

    detected="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}')"
    if valid_ipv4 "$detected" && [[ "$detected" != 127.* ]]; then
        printf '%s' "$detected"
        return
    fi

    detected="$(hostname -I 2>/dev/null | tr ' ' '\n' | awk '/^[0-9]+\./ && $0 !~ /^127\./ {print; exit}')"
    if valid_ipv4 "$detected"; then
        printf '%s' "$detected"
        return
    fi

    die "Could not detect a LAN IPv4 address. Run with --ip 192.168.x.x."
}

read_env_value() {
    local key="$1"
    local env_path="${REPO_DIR}/.env"
    [[ -f "$env_path" ]] || return 0
    awk -F= -v wanted="$key" '
        /^[[:space:]]*#/ { next }
        $1 ~ "^[[:space:]]*" wanted "[[:space:]]*$" {
            value = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            gsub(/^\"|\"$/, "", value)
            gsub(/^\x27|\x27$/, "", value)
            print value
            exit
        }
    ' "$env_path"
}

upsert_env_value() {
    local key="$1"
    local value="$2"
    local env_path="${REPO_DIR}/.env"
    local temporary

    if [[ ! -f "$env_path" ]]; then
        if [[ -f "${REPO_DIR}/.env.example" ]]; then
            cp "${REPO_DIR}/.env.example" "$env_path"
        else
            touch "$env_path"
        fi
    fi

    temporary="$(mktemp)"
    awk -v wanted="$key" -v replacement="${key}=${value}" '
        BEGIN { found = 0 }
        $0 ~ "^[[:space:]]*" wanted "[[:space:]]*=" {
            print replacement
            found = 1
            next
        }
        { print }
        END { if (!found) print replacement }
    ' "$env_path" > "$temporary"
    mv "$temporary" "$env_path"
}

update_env_for_host() {
    local existing_host
    existing_host="$(read_env_value LAN_HOST_IP || true)"
    if [[ -f "${REPO_DIR}/.env" ]]; then
        backup_if_present "${REPO_DIR}/.env"
    fi
    upsert_env_value "LAN_HOST_IP" "$HOST_IP"
    upsert_env_value "SRS_HLS_BASE_URL" "http://${HOST_IP}:${NGINX_PORT}"
    upsert_env_value "CORS_ORIGINS" "[\"http://${HOST_IP}:${FRONTEND_PORT}\", \"http://localhost:${FRONTEND_PORT}\"]"
    echo "LAN_HOST_IP updated from '${existing_host:-not set}' to '${HOST_IP}'."
}

backup_if_present() {
    local path="$1"
    if sudo test -e "$path" || sudo test -L "$path"; then
        local backup="${path}.backup.$(date +%Y%m%d%H%M%S)"
        sudo cp -a "$path" "$backup"
        echo "Backed up $path to $backup"
    fi
}

write_site_config() {
    local temporary
    temporary="$(mktemp)"
    trap 'rm -f "$temporary"' RETURN

    cat > "$temporary" <<EOF
# Managed by Hominsu scripts/install_nginx_ubuntu.sh
# RTMP ingest remains on SRS: rtmp://${HOST_IP}:${SRS_RTMP_PORT}/live/<stream_key>

map \$http_upgrade \$hominsu_connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen ${NGINX_PORT};
    server_name ${SERVER_NAME};

    # FastAPI REST API.
    location /api/ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # FastAPI native WebSockets.
    location /ws/ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$hominsu_connection_upgrade;
        proxy_set_header Host \$host;
        proxy_read_timeout 3600s;
    }

    # SRS HLS playlists and MPEG-TS segments.
    location /live/ {
        proxy_pass http://127.0.0.1:${SRS_HTTP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        add_header Access-Control-Allow-Origin * always;
        add_header Cache-Control no-cache always;
    }

    location /health {
        proxy_pass http://127.0.0.1:${APP_PORT}/health;
        proxy_set_header Host \$host;
    }

    location / {
        default_type application/json;
        return 404 '{"detail":"Hominsu Nginx proxy is running"}';
    }
}
EOF

    sudo install -o root -g root -m 0644 "$temporary" "$SITE_AVAILABLE"
    rm -f "$temporary"
    trap - RETURN
}

while (($# > 0)); do
    case "$1" in
        --ip)
            (($# >= 2)) || die "--ip requires an address"
            HOST_IP="$2"
            shift 2
            ;;
        --server-name)
            (($# >= 2)) || die "--server-name requires a value"
            SERVER_NAME="$2"
            shift 2
            ;;
        --nginx-port)
            (($# >= 2)) || die "--nginx-port requires a port"
            NGINX_PORT="$2"
            shift 2
            ;;
        --frontend-port)
            (($# >= 2)) || die "--frontend-port requires a port"
            FRONTEND_PORT="$2"
            shift 2
            ;;
        --configure-ufw)
            CONFIGURE_UFW=1
            shift
            ;;
        --no-ufw)
            CONFIGURE_UFW=0
            shift
            ;;
        --enable-ufw)
            CONFIGURE_UFW=1
            ENABLE_UFW=1
            shift
            ;;
        --skip-env)
            SKIP_ENV=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

command -v sudo >/dev/null 2>&1 || die "sudo is required"
command -v apt-get >/dev/null 2>&1 || die "This installer requires Ubuntu/Debian apt-get"
command -v systemctl >/dev/null 2>&1 || die "systemctl is required"

valid_port "$NGINX_PORT" || die "Invalid Nginx port: $NGINX_PORT"
valid_port "$FRONTEND_PORT" || die "Invalid frontend port: $FRONTEND_PORT"
if [[ -z "$HOST_IP" ]]; then
    HOST_IP="$(read_env_value LAN_HOST_IP || true)"
fi
if [[ -z "$HOST_IP" ]]; then
    HOST_IP="$(detect_host_ip)"
fi
valid_ipv4 "$HOST_IP" || die "Invalid IPv4 address: $HOST_IP"

echo "Installing Nginx on Ubuntu..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

if (( ! SKIP_ENV )); then
    update_env_for_host
fi

backup_if_present "$SITE_AVAILABLE"
write_site_config

# Keep Ubuntu's default site from competing with the Hominsu server block. Back it up first.
if sudo test -e /etc/nginx/sites-enabled/default || sudo test -L /etc/nginx/sites-enabled/default; then
    backup_if_present "/etc/nginx/sites-enabled/default"
    sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo ln -sfn "$SITE_AVAILABLE" "$SITE_ENABLED"

sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

if (( CONFIGURE_UFW )); then
    if ! command -v ufw >/dev/null 2>&1; then
        echo "UFW is not installed; installing it now..."
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw
    fi
    sudo ufw allow "${SRS_RTMP_PORT}/tcp" comment 'Hominsu SRS RTMP ingest'
    sudo ufw allow "${NGINX_PORT}/tcp" comment 'Hominsu Nginx LAN proxy'
    echo "UFW rules added for TCP ${SRS_RTMP_PORT} and ${NGINX_PORT}."
    if (( ENABLE_UFW )); then
        sudo ufw allow OpenSSH
        sudo ufw --force enable
        echo "UFW enabled after allowing OpenSSH."
    elif sudo ufw status | grep -qi "Status: inactive"; then
        echo "UFW is installed but inactive. It was not enabled automatically; verify SSH access, then run:"
        echo "  sudo ufw enable"
    fi
else
    echo "UFW was not changed. If enabled, allow TCP ${SRS_RTMP_PORT} and ${NGINX_PORT} from the LAN."
fi

cat <<INFO

Hominsu Nginx setup complete.

Server IP:             ${HOST_IP}
Insta360 RTMP:         rtmp://${HOST_IP}:${SRS_RTMP_PORT}/live/insta-001
HLS through Nginx:     http://${HOST_IP}:${NGINX_PORT}/live/insta-001.m3u8
FastAPI through Nginx: http://${HOST_IP}:${NGINX_PORT}/api/v1
Health check:          http://${HOST_IP}:${NGINX_PORT}/health
Nginx site:            ${SITE_AVAILABLE}

Start FastAPI with --host 0.0.0.0 and keep SRS publishing port ${SRS_RTMP_PORT}.
INFO
