import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContentType(str, enum.Enum):
    VOD = "VOD"
    LIVE_360 = "LIVE_360"
    SHORT_FORM = "SHORT_FORM"


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type"), nullable=False, default=ContentType.VOD
    )
    stream_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # HLS .m3u8 or WebRTC URL
    price_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    viewer_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    devices: Mapped[list["Device"]] = relationship(  # noqa: F821
        back_populates="current_content"
    )
