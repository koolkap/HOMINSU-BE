from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)


class Role(db.Model):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(32), unique=True, nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    role_id: Mapped[int] = mapped_column(db.ForeignKey("roles.id"), nullable=False)
    role: Mapped[Role] = relationship(back_populates="users")
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Creator(TimestampMixin, db.Model):
    __tablename__ = "creators"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(db.Text)
    avatar_url: Mapped[str | None] = mapped_column(db.String(500))
    contents: Mapped[list["Content"]] = relationship(back_populates="creator")


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(db.String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    contents: Mapped[list["Content"]] = relationship(back_populates="category")


class Content(TimestampMixin, db.Model):
    __tablename__ = "contents"
    __table_args__ = (
        CheckConstraint("points_price >= 0", name="points_price_nonnegative"),
        CheckConstraint("cash_price >= 0", name="cash_price_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(db.String(200), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    media_url: Mapped[str] = mapped_column(db.String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(db.String(500))
    content_type: Mapped[str] = mapped_column(db.String(32), default="vr", nullable=False)
    is_featured: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(default=True, nullable=False)
    points_price: Mapped[int] = mapped_column(default=0, nullable=False)
    cash_price: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    category_id: Mapped[int] = mapped_column(db.ForeignKey("categories.id"), nullable=False, index=True)
    creator_id: Mapped[int] = mapped_column(db.ForeignKey("creators.id"), nullable=False, index=True)
    category: Mapped[Category] = relationship(back_populates="contents")
    creator: Mapped[Creator] = relationship(back_populates="contents")


class LiveStream(TimestampMixin, db.Model):
    __tablename__ = "live_streams"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(db.String(200), nullable=False)
    stream_url: Mapped[str] = mapped_column(db.String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(db.String(500))
    status: Mapped[str] = mapped_column(db.String(20), default="scheduled", nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    ends_at: Mapped[datetime | None]
    creator_id: Mapped[int] = mapped_column(db.ForeignKey("creators.id"), nullable=False)
    creator: Mapped[Creator] = relationship()


class Wallet(TimestampMixin, db.Model):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("points_balance >= 0", name="points_balance_nonnegative"),
        CheckConstraint("cash_balance >= 0", name="cash_balance_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    points_balance: Mapped[int] = mapped_column(default=0, nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    user: Mapped[User] = relationship(back_populates="wallet")
    transactions: Mapped[list["WalletTransaction"]] = relationship(back_populates="wallet")


class WalletPackage(TimestampMixin, db.Model):
    __tablename__ = "wallet_packages"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), nullable=False)
    points: Mapped[int] = mapped_column(nullable=False)
    bonus_points: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class WalletTransaction(TimestampMixin, db.Model):
    __tablename__ = "wallet_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(db.ForeignKey("wallets.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(db.String(32), nullable=False)
    points_delta: Mapped[int] = mapped_column(default=0, nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    reference: Mapped[str | None] = mapped_column(db.String(120), unique=True)
    description: Mapped[str | None] = mapped_column(db.String(255))
    wallet: Mapped[Wallet] = relationship(back_populates="transactions")


class ContentUnlock(TimestampMixin, db.Model):
    __tablename__ = "content_unlocks"
    __table_args__ = (UniqueConstraint("user_id", "content_id", name="uq_content_unlock_user_content"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(db.ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    method: Mapped[str] = mapped_column(db.String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(db.Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    user: Mapped[User] = relationship()
    content: Mapped[Content] = relationship()


class Venue(TimestampMixin, db.Model):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(db.String(255))
    devices: Mapped[list["VenueDevice"]] = relationship(back_populates="venue")


class VenueDevice(TimestampMixin, db.Model):
    __tablename__ = "venue_devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_key: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    headset_model: Mapped[str | None] = mapped_column(db.String(80))
    status: Mapped[str] = mapped_column(db.String(20), default="offline", nullable=False)
    app_version: Mapped[str | None] = mapped_column(db.String(40))
    battery_level: Mapped[int | None]
    ip_address: Mapped[str | None] = mapped_column(db.String(45))
    last_seen_at: Mapped[datetime | None]
    venue_id: Mapped[int] = mapped_column(db.ForeignKey("venues.id"), nullable=False)
    venue: Mapped[Venue] = relationship(back_populates="devices")
    actions: Mapped[list["DeviceAction"]] = relationship(back_populates="device")


class DeviceAction(TimestampMixin, db.Model):
    __tablename__ = "device_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(db.ForeignKey("venue_devices.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(db.String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), default="pending", nullable=False)
    requested_by_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    device: Mapped[VenueDevice] = relationship(back_populates="actions")


class DeviceSync(TimestampMixin, db.Model):
    __tablename__ = "device_syncs"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(db.ForeignKey("venue_devices.id"), nullable=False, index=True)
    sync_token: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    payload: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)
    device: Mapped[VenueDevice] = relationship()
