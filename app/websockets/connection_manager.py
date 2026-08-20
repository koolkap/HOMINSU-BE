"""WebSocket connection manager for the VR fleet.

Tracks two kinds of clients:
- VR headset connections (keyed by device_id): receive SYNC_PLAY commands, send heartbeats.
- Operator console connections: receive telemetry / live-stream events, send control commands.
"""

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("hominsh.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.device_connections: dict[str, WebSocket] = {}
        self.operator_connections: set[WebSocket] = set()

    # --- Connection lifecycle -------------------------------------------

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            # Drop a stale socket if the device reconnects.
            stale = self.device_connections.get(device_id)
            if stale is not None and stale is not websocket:
                try:
                    await stale.close()
                except Exception:
                    pass
            self.device_connections[device_id] = websocket
        logger.info("Device connected: %s (%d devices online)", device_id, len(self.device_connections))

    async def disconnect_device(self, device_id: str) -> None:
        async with self._lock:
            self.device_connections.pop(device_id, None)
        logger.info("Device disconnected: %s", device_id)

    async def connect_operator(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.operator_connections.add(websocket)
        logger.info("Operator connected (%d operators)", len(self.operator_connections))

    async def disconnect_operator(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.operator_connections.discard(websocket)

    # --- Messaging -------------------------------------------------------

    async def broadcast_to_operators(self, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self.operator_connections)
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect_operator(ws)

    async def send_to_device(self, device_id: str, message: dict[str, Any]) -> bool:
        async with self._lock:
            ws = self.device_connections.get(device_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            await self.disconnect_device(device_id)
            return False

    async def send_sync_play(self, device_ids: list[str], video_url: str) -> dict[str, bool]:
        """Broadcast a SYNC_PLAY command to the given devices. Returns per-device delivery."""
        timestamp = time.time()
        payload = {"command": "SYNC_PLAY", "video_url": video_url, "timestamp": timestamp}
        results: dict[str, bool] = {}
        for device_id in device_ids:
            results[device_id] = await self.send_to_device(device_id, payload)
        return results


manager = ConnectionManager()
