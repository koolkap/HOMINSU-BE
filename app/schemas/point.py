import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.point import TransactionType


class RechargeRequest(BaseModel):
    amount_krw: int = Field(gt=0, description="Payment in KRW; converted at 1.1x to points")
    description: str | None = None


class DeductRequest(BaseModel):
    amount: int = Field(gt=0, description="Points to spend")
    description: str | None = None
    content_id: uuid.UUID | None = None


class TransactionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    type: TransactionType
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    points_balance: int
    transaction: TransactionOut
