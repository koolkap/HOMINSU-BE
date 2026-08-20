import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.content import Content, ContentType
from app.models.user import User
from app.api.v1.endpoints.points import _spend_points
from app.schemas.content import ContentCreate, ContentOut, ContentUpdate, PurchaseOut

router = APIRouter(prefix="/contents", tags=["contents"])


@router.post("", response_model=ContentOut, status_code=status.HTTP_201_CREATED)
async def create_content(
    payload: ContentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Content:
    content = Content(**payload.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.get("", response_model=list[ContentOut])
async def list_contents(
    type: ContentType | None = Query(default=None),
    live_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> list[Content]:
    query = select(Content).order_by(Content.created_at.desc())
    if type is not None:
        query = query.where(Content.type == type)
    if live_only:
        query = query.where(Content.is_live.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{content_id}", response_model=ContentOut)
async def get_content(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Content:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content


@router.patch("/{content_id}", response_model=ContentOut)
async def update_content(
    content_id: uuid.UUID,
    payload: ContentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Content:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)
    return content


@router.post("/{content_id}/purchase", response_model=PurchaseOut)
async def purchase_content(
    content_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseOut:
    """Unlock premium 360 content by spending points."""
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content not found")

    if content.price_points <= 0:
        spent, balance = 0, current_user.points_balance
    else:
        tx = await _spend_points(  # noqa: F841 (kept for symmetry; balance read below)
            db, current_user, content.price_points, f"Unlock content: {content.title}"
        )
        spent, balance = content.price_points, current_user.points_balance

    return PurchaseOut(
        content_id=content.id,
        title=content.title,
        media_url=content.media_url,
        points_spent=spent,
        remaining_balance=balance,
    )


@router.post("/{content_id}/view")
async def register_view(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Called by the player when playback starts; bumps the live viewer count."""
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content not found")
    content.viewer_count += 1
    await db.commit()
    return {"content_id": content_id, "viewer_count": content.viewer_count}
