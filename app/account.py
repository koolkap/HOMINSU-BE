from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from .auth import current_user, serialize_user
from .errors import error_response
from .extensions import db
from .models import Content, ContentUnlock, Wallet, WalletPackage, WalletTransaction


bp = Blueprint("account", __name__)


def wallet_data(wallet: Wallet) -> dict:
    return {"id": wallet.id, "points_balance": wallet.points_balance, "cash_balance": str(wallet.cash_balance)}


def active_user_or_error():
    user = current_user()
    if not user or not user.is_active:
        return None, error_response("authentication_required", "A valid active account is required.", 401)
    return user, None


@bp.get("/me")
@jwt_required()
def me():
    user, error = active_user_or_error()
    if error:
        return error
    return jsonify({"data": serialize_user(user)})


@bp.get("/wallet")
@jwt_required()
def wallet():
    user, error = active_user_or_error()
    if error:
        return error
    return jsonify({"data": wallet_data(user.wallet)})


@bp.get("/wallet/packages")
def packages():
    items = db.session.scalars(db.select(WalletPackage).where(WalletPackage.is_active.is_(True)).order_by(WalletPackage.price)).all()
    return jsonify({"data": [{"id": x.id, "code": x.code, "name": x.name, "price": str(x.price), "points": x.points, "bonus_points": x.bonus_points} for x in items]})


@bp.post("/wallet/topups")
@jwt_required()
def topup():
    user, error = active_user_or_error()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    package_id = body.get("package_id")
    reference = str(body.get("reference", "")).strip()
    if not isinstance(package_id, int) or not reference:
        return error_response("validation_error", "package_id and a payment reference are required.", 400)
    package = db.session.get(WalletPackage, package_id)
    if not package or not package.is_active:
        return error_response("not_found", "Wallet package was not found.", 404)
    if db.session.scalar(db.select(WalletTransaction).where(WalletTransaction.reference == reference)):
        return error_response("conflict", "Payment reference has already been processed.", 409)
    wallet = db.session.scalar(db.select(Wallet).where(Wallet.user_id == user.id).with_for_update())
    credited = package.points + package.bonus_points
    wallet.points_balance += credited
    transaction = WalletTransaction(wallet=wallet, kind="topup", points_delta=credited, reference=reference, description=package.name)
    db.session.add(transaction)
    db.session.commit()
    return jsonify({"data": {"transaction_id": transaction.id, "wallet": wallet_data(wallet)}}), 201


@bp.post("/content/<int:content_id>/unlock")
@jwt_required()
def unlock(content_id: int):
    user, error = active_user_or_error()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    method = body.get("method")
    if method not in {"ad", "points", "cash"}:
        return error_response("validation_error", "method must be ad, points, or cash.", 400)
    content = db.session.get(Content, content_id)
    if not content or not content.is_published:
        return error_response("not_found", "Content was not found.", 404)
    existing = db.session.scalar(db.select(ContentUnlock).where(ContentUnlock.user_id == user.id, ContentUnlock.content_id == content.id))
    if existing:
        return jsonify({"data": {"id": existing.id, "content_id": content.id, "method": existing.method, "already_unlocked": True}})

    wallet = db.session.scalar(db.select(Wallet).where(Wallet.user_id == user.id).with_for_update())
    amount = Decimal("0.00")
    transaction = None
    if method == "points":
        if wallet.points_balance < content.points_price:
            return error_response("insufficient_funds", "Insufficient points balance.", 409)
        wallet.points_balance -= content.points_price
        amount = Decimal(content.points_price)
        transaction = WalletTransaction(wallet=wallet, kind="unlock", points_delta=-content.points_price, description=content.title)
    elif method == "cash":
        if wallet.cash_balance < content.cash_price:
            return error_response("insufficient_funds", "Insufficient cash balance.", 409)
        wallet.cash_balance -= content.cash_price
        amount = content.cash_price
        transaction = WalletTransaction(wallet=wallet, kind="unlock", cash_delta=-content.cash_price, description=content.title)
    unlock_record = ContentUnlock(user_id=user.id, content_id=content.id, method=method, amount=amount)
    db.session.add(unlock_record)
    if transaction:
        db.session.add(transaction)
    db.session.commit()
    return jsonify({"data": {"id": unlock_record.id, "content_id": content.id, "method": method, "already_unlocked": False, "wallet": wallet_data(wallet)}}), 201
