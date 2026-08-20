import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.device import DeviceStatus


class DeviceRegister(BaseModel):
    id: str = Field(min_length=1, max_length=64, examples=["HS-01"])
    model: str = Field(default="Unknown", examples=["Meta Quest 3", "Vive Focus 3"])
    status: DeviceStatus = DeviceStatus.OFFLINE
    battery_level: float = Field(default=0.0, ge=0, le=100)
    ip_address: str | None = None
    firmware_version: str | None = None
    current_content_id: uuid.UUID | None = None


class DeviceOut(BaseModel):
    id: str
    model: str
    status: DeviceStatus
    battery_level: float
    ip_address: str | None
    firmware_version: str | None
    current_content_id: uuid.UUID | None
    last_heartbeat: datetime | None

    model_config = {"from_attributes": True}


class HeartbeatPayload(BaseModel):
    battery_level: float = Field(ge=0, le=100)
    ip_address: str
    status: DeviceStatus = DeviceStatus.ONLINE


class TriggerSyncPlay(BaseModel):
    device_ids: list[str] = Field(min_length=1)
    video_url: str
