"""add media assets

Revision ID: 9f7c2a1d4b83
Revises: 6b922d0ca162
Create Date: 2026-07-11 22:45:00

"""
from alembic import op
import sqlalchemy as sa


revision = "9f7c2a1d4b83"
down_revision = "6b922d0ca162"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_path", sa.String(length=1024), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("is_showcase_ready", sa.Boolean(), nullable=False),
        sa.Column("storage_state", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("media_kind IN ('image', 'video')", name=op.f("ck_media_assets_media_kind_valid")),
        sa.CheckConstraint("provider IN ('s3', 'supabase')", name=op.f("ck_media_assets_provider_valid")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_media_assets_size_bytes_positive")),
        sa.CheckConstraint("storage_state IN ('ready', 'cleanup_required')", name=op.f("ck_media_assets_storage_state_valid")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_media_assets_owner_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
        sa.UniqueConstraint("provider", "bucket", "object_path", name="uq_media_asset_storage_object"),
    )
    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_media_assets_is_showcase_ready"), ["is_showcase_ready"], unique=False)
        batch_op.create_index(batch_op.f("ix_media_assets_owner_id"), ["owner_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_media_assets_storage_state"), ["storage_state"], unique=False)


def downgrade():
    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_assets_storage_state"))
        batch_op.drop_index(batch_op.f("ix_media_assets_owner_id"))
        batch_op.drop_index(batch_op.f("ix_media_assets_is_showcase_ready"))
    op.drop_table("media_assets")
