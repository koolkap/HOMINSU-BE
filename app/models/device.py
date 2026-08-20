import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DeviceStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class Device(Base):
    """VR headset fleet registry."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. 'HS-01'
    model: Mapped[str] = mapped_column(String(255), default="Unknown")
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status"), default=DeviceStatus.OFFLINE, nullable=False
    )
    battery_level: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0-100
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_content_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contents.id"), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_content: Mapped["Content"] = relationship(  # noqa: F821
        back_populates="devices"
    )


# Keep the linter happy for the lazy forward reference above.
from app.models.content import Content  # noqa: E402, F401
