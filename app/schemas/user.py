import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SocialLoginRequest(BaseModel):
    """Payload for fast social login/signup (e.g. Kakao credentials)."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    provider: str = Field(default="local", pattern="^(kakao|google|local)$")


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    provider: str
    points_balance: int
    subscription_tier: str = "FREE"
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
