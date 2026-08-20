"""Create the initial Hominsu VR Studio schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    content_type = postgresql.ENUM(
        "VOD", "LIVE_360", "SHORT_FORM", name="content_type", create_type=False
    )
    device_status = postgresql.ENUM(
        "ONLINE", "OFFLINE", "MAINTENANCE", name="device_status", create_type=False
    )
    transaction_type = postgresql.ENUM(
        "RECHARGE", "SPEND", "BONUS", name="transaction_type", create_type=False
    )

    bind = op.get_bind()
    content_type.create(bind, checkfirst=True)
    device_status.create(bind, checkfirst=True)
    transaction_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("points_balance", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("type", content_type, nullable=False),
        sa.Column("stream_key", sa.String(length=255), nullable=True),
        sa.Column("media_url", sa.String(length=1000), nullable=True),
        sa.Column("price_points", sa.Integer(), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=False),
        sa.Column("viewer_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_key"),
    )
    op.create_index("ix_contents_stream_key", "contents", ["stream_key"], unique=False)

    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", device_status, nullable=False),
        sa.Column("battery_level", sa.Float(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("firmware_version", sa.String(length=64), nullable=True),
        sa.Column("current_content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["current_content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "point_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_point_transactions_user_id", "point_transactions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_point_transactions_user_id", table_name="point_transactions")
    op.drop_table("point_transactions")
    op.drop_table("devices")
    op.drop_index("ix_contents_stream_key", table_name="contents")
    op.drop_table("contents")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    postgresql.ENUM(name="transaction_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="device_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="content_type").drop(bind, checkfirst=True)
