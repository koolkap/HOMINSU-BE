from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import SocialLoginRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/social-login", response_model=Token, status_code=status.HTTP_200_OK)
async def social_login(payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """Fast login/signup: upsert the user by email and return a JWT access token."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=payload.email, name=payload.name, provider=payload.provider, points_balance=0)
        db.add(user)
        await db.flush()
    elif user.provider != payload.provider or user.name != payload.name:
        user.provider = payload.provider
        user.name = payload.name
        await db.flush()

    await db.commit()
    await db.refresh(user)

    return Token(
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Profile of the logged-in user, including points balance and subscription tier."""
    return UserOut.model_validate(current_user)
