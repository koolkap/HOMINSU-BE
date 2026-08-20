import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.content import ContentType


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    type: ContentType = ContentType.VOD
    stream_key: str | None = Field(default=None, max_length=255)
    media_url: str | None = Field(default=None, max_length=1000)
    price_points: int = Field(default=0, ge=0)


class ContentUpdate(BaseModel):
    title: str | None = None
    media_url: str | None = None
    price_points: int | None = Field(default=None, ge=0)


class ContentOut(BaseModel):
    id: uuid.UUID
    title: str
    type: ContentType
    stream_key: str | None
    media_url: str | None
    price_points: int
    is_live: bool
    viewer_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOut(BaseModel):
    content_id: uuid.UUID
    title: str
    media_url: str | None
    points_spent: int
    remaining_balance: int
