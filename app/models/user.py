import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(32), default="local")  # 'kakao' | 'google' | 'local'
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    transactions: Mapped[list["PointTransaction"]] = relationship(  # noqa: F821
        back_populates="user", cascade="save-update, merge"
    )
