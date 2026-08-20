import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.models.device import Device, DeviceStatus
from app.schemas.device import DeviceOut, DeviceRegister, HeartbeatPayload, TriggerSyncPlay
from app.websockets.connection_manager import manager

logger = logging.getLogger("hominsh.fleet")

router = APIRouter(prefix="/fleet", tags=["fleet"])
ws_router = APIRouter()


# ---------------------------------------------------------------------------
# REST: fleet registry
# ---------------------------------------------------------------------------

@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    status_filter: DeviceStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    query = select(Device).order_by(Device.id)
    if status_filter is not None:
        query = query.where(Device.status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(payload: DeviceRegister, db: AsyncSession = Depends(get_db)) -> Device:
    existing = await db.get(Device, payload.id)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Device {payload.id} already registered")
    device = Device(**payload.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/devices/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)) -> Device:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------

async def _update_device_row(device_id: str, **fields) -> Device | None:
    """Upsert telemetry on the devices row outside a request-scoped session."""
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
        if device is None:
            device = Device(
                id=device_id,
                model=fields.pop("model", "Unknown"),
            )
            db.add(device)
        for key, value in fields.items():
            setattr(device, key, value)
        await db.commit()
        return device


# ---------------------------------------------------------------------------
# WebSocket: VR headset channel (/ws/device/{device_id})
# ---------------------------------------------------------------------------

@ws_router.websocket("/ws/device/{device_id}")
async def device_channel(websocket: WebSocket, device_id: str) -> None:
    """VR headset connection: receives heartbeats, dispatches SYNC_PLAY commands."""
    await manager.connect_device(device_id, websocket)
    await _update_device_row(device_id, status=DeviceStatus.ONLINE, last_heartbeat=datetime.now(timezone.utc))
    await manager.broadcast_to_operators({"event": "device_connected", "device_id": device_id})
    try:
        while True:
            message = await websocket.receive_json()
            event = message.get("event")

            if event == "heartbeat":
                try:
                    payload = HeartbeatPayload(
                        battery_level=message["battery_level"],
                        ip_address=message["ip_address"],
                        status=DeviceStatus(message.get("status", "ONLINE")),
                    )
                except (KeyError, ValueError) as exc:
                    await websocket.send_json({"event": "error", "detail": f"Invalid heartbeat: {exc}"})
                    continue
                heartbeat_at = datetime.now(timezone.utc)
                await _update_device_row(
                    device_id,
                    battery_level=payload.battery_level,
                    ip_address=payload.ip_address,
                    status=payload.status,
                    last_heartbeat=heartbeat_at,
                )
                await manager.broadcast_to_operators(
                    {
                        "event": "telemetry",
                        "device_id": device_id,
                        "battery_level": payload.battery_level,
                        "ip_address": payload.ip_address,
                        "status": payload.status,
                        "last_heartbeat": heartbeat_at.isoformat(),
                    }
                )
            else:
                await websocket.send_json({"event": "error", "detail": f"Unknown event: {event!r}"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect_device(device_id)
        await _update_device_row(device_id, status=DeviceStatus.OFFLINE)
        await manager.broadcast_to_operators({"event": "device_disconnected", "device_id": device_id})


# ---------------------------------------------------------------------------
# WebSocket: Operator console channel (/ws/operator)
# ---------------------------------------------------------------------------

@ws_router.websocket("/ws/operator")
async def operator_channel(websocket: WebSocket) -> None:
    """Operator dashboard connection: receives telemetry, sends control commands."""
    await manager.connect_operator(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            event = message.get("event")

            if event == "trigger_sync_play":
                try:
                    payload = TriggerSyncPlay(
                        device_ids=message["device_ids"], video_url=message["video_url"]
                    )
                except (KeyError, ValueError) as exc:
                    await websocket.send_json({"event": "error", "detail": f"Invalid command: {exc}"})
                    continue
                delivery = await manager.send_sync_play(payload.device_ids, payload.video_url)
                await websocket.send_json(
                    {"event": "sync_play_dispatched", "video_url": payload.video_url, "delivery": delivery}
                )
            else:
                await websocket.send_json({"event": "error", "detail": f"Unknown event: {event!r}"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect_operator(websocket)
