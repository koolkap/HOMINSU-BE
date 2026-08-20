import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransactionType(str, enum.Enum):
    RECHARGE = "RECHARGE"
    SPEND = "SPEND"
    BONUS = "BONUS"


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # positive = recharge/bonus, negative = spend
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821
