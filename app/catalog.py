from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from .errors import error_response
from .extensions import db
from .models import Category, Content, LiveStream


bp = Blueprint("catalog", __name__)


def serialize_content(item: Content) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "media_url": item.media_url,
        "thumbnail_url": item.thumbnail_url,
        "content_type": item.content_type,
        "is_featured": item.is_featured,
        "points_price": item.points_price,
        "cash_price": str(item.cash_price),
        "category": {"id": item.category.id, "slug": item.category.slug, "name": item.category.name},
        "creator": {"id": item.creator.id, "name": item.creator.name},
    }


@bp.get("/catalog/categories")
def categories():
    items = db.session.scalars(db.select(Category).order_by(Category.sort_order, Category.name)).all()
    return jsonify({"data": [{"id": x.id, "slug": x.slug, "name": x.name, "description": x.description} for x in items]})


@bp.get("/content")
def content_list():
    stmt = db.select(Content).options(joinedload(Content.category), joinedload(Content.creator)).where(Content.is_published.is_(True))
    category = request.args.get("category", type=str)
    feed = request.args.get("feed", type=str)
    query = request.args.get("q", type=str)
    if category:
        stmt = stmt.join(Content.category).where(Category.slug == category)
    if feed == "featured":
        stmt = stmt.where(Content.is_featured.is_(True))
    elif feed == "free":
        stmt = stmt.where(Content.points_price == 0, Content.cash_price == 0)
    elif feed not in {None, "latest"}:
        return error_response("validation_error", "feed must be latest, featured, or free.", 400)
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(or_(Content.title.ilike(pattern), Content.description.ilike(pattern)))
    items = db.session.scalars(stmt.order_by(Content.created_at.desc()).limit(100)).all()
    return jsonify({"data": [serialize_content(item) for item in items]})


@bp.get("/content/<int:content_id>")
def content_detail(content_id: int):
    stmt = db.select(Content).options(joinedload(Content.category), joinedload(Content.creator)).where(Content.id == content_id, Content.is_published.is_(True))
    item = db.session.scalar(stmt)
    if not item:
        return error_response("not_found", "Content was not found.", 404)
    return jsonify({"data": serialize_content(item)})


@bp.get("/live")
def live_list():
    items = db.session.scalars(db.select(LiveStream).options(joinedload(LiveStream.creator)).where(LiveStream.status.in_(["live", "scheduled"])).order_by(LiveStream.starts_at)).all()
    return jsonify({"data": [{
        "id": item.id, "title": item.title, "stream_url": item.stream_url,
        "thumbnail_url": item.thumbnail_url, "status": item.status,
        "starts_at": item.starts_at.isoformat(), "ends_at": item.ends_at.isoformat() if item.ends_at else None,
        "creator": {"id": item.creator.id, "name": item.creator.name},
    } for item in items]})
