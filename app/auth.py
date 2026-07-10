from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from .errors import error_response
from .extensions import db
from .models import User


bp = Blueprint("auth", __name__)


def current_user() -> User | None:
    identity = get_jwt_identity()
    return db.session.get(User, int(identity)) if identity else None


def operator_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            return error_response("authentication_required", "A valid active account is required.", 401)
        if user.role.name not in {"operator", "admin"}:
            return error_response("forbidden", "Operator access is required.", 403)
        return fn(*args, **kwargs)

    return wrapped


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    if not email or not isinstance(password, str):
        return error_response("validation_error", "Email and password are required.", 400)
    user = db.session.scalar(db.select(User).where(User.email == email))
    if not user or not user.is_active or not user.check_password(password):
        return error_response("invalid_credentials", "Invalid email or password.", 401)
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.name})
    return jsonify({"data": {"access_token": token, "token_type": "Bearer", "user": serialize_user(user)}})


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.name,
    }
