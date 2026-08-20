from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.point import PointTransaction, TransactionType
from app.models.user import User
from app.schemas.point import BalanceOut, DeductRequest, RechargeRequest, TransactionOut

router = APIRouter(prefix="/points", tags=["points"])


async def _spend_points(
    db: AsyncSession, user: User, amount: int, description: str | None
) -> PointTransaction:
    """Shared deduction logic: checks balance, records the SPEND transaction."""
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")
    if user.points_balance < amount:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance: {user.points_balance}P available, {amount}P required",
        )
    user.points_balance -= amount
    tx = PointTransaction(
        user_id=user.id, amount=-amount, type=TransactionType.SPEND, description=description
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("/recharge", response_model=BalanceOut)
async def recharge(
    payload: RechargeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BalanceOut:
    """Purchase points with KRW (e.g. 10,000 KRW -> 11,000P at the 1.1x rate)."""
    points = int(payload.amount_krw * settings.KRW_TO_POINTS_RATE)
    current_user.points_balance += points
    tx = PointTransaction(
        user_id=current_user.id,
        amount=points,
        type=TransactionType.RECHARGE,
        description=payload.description or f"Recharge {payload.amount_krw:,} KRW",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return BalanceOut(points_balance=current_user.points_balance, transaction=tx)


@router.post("/deduct", response_model=BalanceOut)
async def deduct(
    payload: DeductRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BalanceOut:
    """Spend points (unlock premium 360 content, tip during live streams)."""
    tx = await _spend_points(db, current_user, payload.amount, payload.description)
    return BalanceOut(points_balance=current_user.points_balance, transaction=tx)


@router.get("/transactions", response_model=list[TransactionOut])
async def my_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PointTransaction]:
    result = await db.execute(
        select(PointTransaction)
        .where(PointTransaction.user_id == current_user.id)
        .order_by(PointTransaction.created_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())
