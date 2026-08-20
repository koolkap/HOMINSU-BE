"""Configure Hominsu for access from an Insta360 app on the local network.

This script uses only the Python standard library. It detects a private IPv4 address,
prints the URLs required by the camera/player, updates the external-facing values in
.env when --apply is supplied, and writes an optional Nginx reverse-proxy config.

Examples:
    python scripts/setup_lan_network.py
    python scripts/setup_lan_network.py --apply
    python scripts/setup_lan_network.py --ip 192.168.1.25 --apply --start-nginx

The script intentionally does not replace every occurrence of "localhost":
- PostgreSQL remains localhost because it is reached by FastAPI on the host.
- host.docker.internal remains in srs.conf because SRS runs in Docker and calls FastAPI.
- Public RTMP/HLS/API/WebSocket URLs use the detected LAN address.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path


DEFAULT_STREAM_KEY = "insta-001"
DEFAULT_NGINX_PORT = 8088
DEFAULT_FRONTEND_PORT = 3000
ENV_FILE = ".env"
ENV_BACKUP = ".env.lan.backup"
NGINX_FILE = "nginx.local.conf"


def is_usable_private_ipv4(value: str) -> bool:
    """Return True for a routable RFC1918 address, excluding APIPA/link-local IPs."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return isinstance(address, ipaddress.IPv4Address) and address.is_private and not address.is_loopback


def detect_ipv4_addresses() -> list[str]:
    """Find private IPv4 candidates using the OS hostname and Windows ipconfig output."""
    candidates: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if is_usable_private_ipv4(value) and value not in candidates:
            candidates.append(value)

    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
        for value in addresses:
            add(value)
    except OSError:
        pass

    # socket.gethostbyname_ex can omit the active Wi-Fi adapter on Windows. ipconfig
    # is the same source the developer would inspect manually, so use it as a fallback.
    if os.name == "nt":
        try:
            output = subprocess.run(
                ["ipconfig"], capture_output=True, text=True, check=False
            ).stdout
            for value in re.findall(r"(?:IPv4[^:]*|IP Address)[^:]*:\s*([0-9.]+)", output):
                add(value)
        except OSError:
            pass

    # The UDP socket is never connected to the Internet; connect() only asks the OS
    # which local interface it would use for an outbound route.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 80))
            add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass

    return candidates


def detect_default_route_ipv4() -> str | None:
    """Return the IPv4 address selected by the OS for the normal network route.

    Windows often reports WSL/Docker adapters alongside the real Wi-Fi adapter.
    A lexical/private-range sort cannot distinguish those virtual interfaces, but
    a UDP socket connected to a non-routable address lets the OS reveal the local
    address it would use for outbound traffic without sending any packet.
    """
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 80))
            value = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        return None

    return value if is_usable_private_ipv4(value) else None


def candidate_rank(value: str) -> tuple[int, str]:
    """Prefer common Wi-Fi/LAN ranges over Docker/WSL's 172.16/12 adapters."""
    address = ipaddress.ip_address(value)
    if str(address).startswith("192.168."):
        return (0, value)
    if str(address).startswith("10."):
        return (1, value)
    if isinstance(address, ipaddress.IPv4Address) and 172 <= int(str(address).split(".")[1]) <= 31:
        return (2, value)
    return (3, value)


def choose_ip(explicit_ip: str | None) -> str:
    if explicit_ip:
        if not is_usable_private_ipv4(explicit_ip):
            raise SystemExit(f"Not a usable private IPv4 address: {explicit_ip}")
        return explicit_ip

    candidates = detect_ipv4_addresses()
    if not candidates:
        raise SystemExit(
            "No private IPv4 address found. Run ipconfig and retry with --ip 192.168.x.x."
        )
    if len(candidates) > 1:
        print("Multiple private IPv4 addresses found:")
        for index, value in enumerate(candidates, start=1):
            print(f"  {index}. {value}")
    # Prefer the adapter selected by the OS for the default route. This avoids
    # choosing a WSL/Docker address such as 172.24.x.x over the reachable Wi-Fi
    # address when both are private IPv4 candidates.
    routed_ip = detect_default_route_ipv4()
    selected = routed_ip if routed_ip in candidates else sorted(candidates, key=candidate_rank)[0]
    if len(candidates) > 1:
        print(f"Using {selected}. If this is not the Wi-Fi/LAN adapter, rerun with --ip.")
    return selected


def read_env(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def upsert_env(lines: list[str], key: str, value: str) -> list[str]:
    """Replace an env assignment while preserving unrelated lines/comments."""
    assignment = f"{key}={value}"
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = assignment
            return lines
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(assignment)
    return lines


def nginx_config(host_ip: str, nginx_port: int, stream_key: str) -> str:
    """Render a single-server Nginx config for API, WebSocket, and HLS proxying."""
    return f"""# Generated by scripts/setup_lan_network.py
# This is an HTTP reverse proxy. RTMP ingest continues to use SRS on port 1935.

events {{}}

http {{
    default_type  application/octet-stream;
    types {{
        application/vnd.apple.mpegurl m3u8;
        video/mp2t ts;
    }}

    map $http_upgrade $connection_upgrade {{
        default upgrade;
        ''      close;
    }}

    server {{
        listen       {nginx_port};
        server_name  {host_ip} localhost;

        # FastAPI REST API.
        location /api/ {{
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        # FastAPI native WebSockets.
        location /ws/ {{
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_read_timeout 3600s;
        }}

        # SRS-generated HLS playlists and segments.
        location /live/ {{
            proxy_pass http://127.0.0.1:8080;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            add_header Access-Control-Allow-Origin * always;
            add_header Cache-Control no-cache always;
        }}

        location / {{
            default_type application/json;
            return 404 '{{"detail":"Hominsu LAN proxy is running"}}';
        }}
    }}
}}
"""


def print_urls(host_ip: str, stream_key: str, nginx_port: int, use_nginx: bool) -> None:
    public_port = nginx_port if use_nginx else 8080
    api_base = f"http://{host_ip}:{nginx_port}" if use_nginx else f"http://{host_ip}:8000"
    hls_url = f"http://{host_ip}:{public_port}/live/{stream_key}.m3u8"
    print()
    print(f"LAN host IP:              {host_ip}")
    print(f"Insta360 RTMP URL:        rtmp://{host_ip}:1935/live/{stream_key}")
    print(f"Direct HLS URL:           http://{host_ip}:8080/live/{stream_key}.m3u8")
    if use_nginx:
        print(f"Nginx HLS URL:            {hls_url}")
        print(f"Nginx API base:           {api_base}")
        print(f"Nginx operator WebSocket: ws://{host_ip}:{nginx_port}/ws/operator")
    else:
        print(f"FastAPI API base:         http://{host_ip}:8000")
        print(f"Operator WebSocket:       ws://{host_ip}:8000/ws/operator")
    print()
    print("Use the RTMP URL in the Insta360 app. The phone and this computer must be on the same LAN.")


def apply_configuration(
    repo: Path,
    host_ip: str,
    stream_key: str,
    nginx_port: int,
    frontend_port: int,
    enable_nginx_urls: bool,
) -> tuple[Path, Path]:
    env_path = repo / ENV_FILE
    backup_path = repo / ENV_BACKUP
    nginx_path = repo / NGINX_FILE

    existing = read_env(env_path)
    if env_path.exists():
        backup_path.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
    elif (repo / ".env.example").exists():
        existing = read_env(repo / ".env.example")

    public_base = f"http://{host_ip}:{nginx_port}" if enable_nginx_urls else f"http://{host_ip}:8080"
    cors = f'["http://{host_ip}:{frontend_port}", "http://localhost:{frontend_port}"]'
    existing = upsert_env(existing, "SRS_HLS_BASE_URL", public_base)
    existing = upsert_env(existing, "CORS_ORIGINS", cors)
    existing = upsert_env(existing, "LAN_HOST_IP", host_ip)
    env_path.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")
    nginx_path.write_text(nginx_config(host_ip, nginx_port, stream_key), encoding="utf-8")
    return env_path, nginx_path


def start_nginx(repo: Path, config_path: Path) -> None:
    executable = shutil.which("nginx") or shutil.which("nginx.exe")
    if executable is None:
        raise SystemExit(
            "Nginx executable was not found in PATH. Install Nginx, or start it manually "
            f"with: nginx -p \"{repo}{os.sep}\" -c \"{config_path}\""
        )
    prefix = str(repo) + os.sep
    test = subprocess.run(
        [executable, "-t", "-p", prefix, "-c", str(config_path)],
        cwd=repo,
        check=False,
    )
    if test.returncode != 0:
        raise SystemExit("Nginx configuration validation failed; see the output above.")
    subprocess.run([executable, "-p", prefix, "-c", str(config_path)], cwd=repo, check=True)
    print("Nginx started with the generated configuration.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", help="LAN IPv4 address; use this when multiple adapters exist")
    parser.add_argument("--stream-key", default=DEFAULT_STREAM_KEY)
    parser.add_argument("--nginx-port", type=int, default=DEFAULT_NGINX_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--apply", action="store_true", help="update .env and write nginx.local.conf")
    parser.add_argument(
        "--no-nginx-urls",
        action="store_true",
        help="set SRS_HLS_BASE_URL to direct SRS port 8080 instead of the Nginx port",
    )
    parser.add_argument("--start-nginx", action="store_true", help="validate and start Nginx after --apply")
    parser.add_argument("--list", action="store_true", help="list detected private IPv4 addresses and exit")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    candidates = detect_ipv4_addresses()
    if args.list:
        for value in candidates:
            print(value)
        return 0

    if args.start_nginx and not args.apply:
        raise SystemExit("--start-nginx requires --apply so the generated config is current.")
    if not 1 <= args.nginx_port <= 65535:
        raise SystemExit("--nginx-port must be between 1 and 65535")
    if not 1 <= args.frontend_port <= 65535:
        raise SystemExit("--frontend-port must be between 1 and 65535")

    repo = Path(__file__).resolve().parents[1]
    host_ip = choose_ip(args.ip)
    use_nginx_urls = not args.no_nginx_urls
    print_urls(host_ip, args.stream_key, args.nginx_port, use_nginx_urls)

    if not args.apply:
        print("Dry run only. Add --apply to update .env and generate nginx.local.conf.")
        return 0

    env_path, nginx_path = apply_configuration(
        repo=repo,
        host_ip=host_ip,
        stream_key=args.stream_key,
        nginx_port=args.nginx_port,
        frontend_port=args.frontend_port,
        enable_nginx_urls=use_nginx_urls,
    )
    print(f"Updated: {env_path}")
    if (repo / ENV_BACKUP).exists():
        print(f"Backup:  {repo / ENV_BACKUP}")
    print(f"Created: {nginx_path}")
    print("Note: srs.conf was intentionally not changed; host.docker.internal is correct for Docker hooks.")
    if args.start_nginx:
        start_nginx(repo, nginx_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
