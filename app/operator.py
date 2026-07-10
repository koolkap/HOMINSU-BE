from uuid import uuid4

from flask import Blueprint, jsonify, request

from .auth import current_user, operator_required
from .errors import error_response
from .extensions import db
from .models import DeviceAction, DeviceSync, VenueDevice, utcnow


bp = Blueprint("operator", __name__)
ALLOWED_ACTIONS = {"launch_content", "stop_content", "restart", "refresh_catalog"}


def serialize_device(device: VenueDevice) -> dict:
    return {
        "id": device.id, "device_key": device.device_key, "name": device.name,
        "status": device.status, "app_version": device.app_version,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "venue": {"id": device.venue.id, "code": device.venue.code, "name": device.venue.name},
    }


@bp.get("/operator/devices")
@operator_required
def devices():
    items = db.session.scalars(db.select(VenueDevice).order_by(VenueDevice.name)).all()
    return jsonify({"data": [serialize_device(item) for item in items]})


@bp.post("/operator/devices/actions")
@operator_required
def create_action():
    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id")
    action_name = body.get("action")
    payload = body.get("payload", {})
    if not isinstance(device_id, int) or action_name not in ALLOWED_ACTIONS or not isinstance(payload, dict):
        return error_response("validation_error", "A valid device_id, action, and object payload are required.", 400)
    device = db.session.get(VenueDevice, device_id)
    if not device:
        return error_response("not_found", "Device was not found.", 404)
    action = DeviceAction(device=device, action=action_name, payload=payload, requested_by_id=current_user().id)
    db.session.add(action)
    db.session.commit()
    return jsonify({"data": {"id": action.id, "device_id": device.id, "action": action.action, "status": action.status, "payload": action.payload}}), 201


@bp.post("/operator/sync")
@operator_required
def sync():
    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id")
    payload = body.get("payload", {})
    if not isinstance(device_id, int) or not isinstance(payload, dict):
        return error_response("validation_error", "A valid device_id and object payload are required.", 400)
    device = db.session.get(VenueDevice, device_id)
    if not device:
        return error_response("not_found", "Device was not found.", 404)
    device.status = body.get("status", "online") if body.get("status", "online") in {"online", "offline", "maintenance"} else "online"
    device.app_version = str(body.get("app_version", device.app_version or ""))[:40] or None
    device.last_seen_at = utcnow()
    record = DeviceSync(device=device, sync_token=uuid4().hex, payload=payload)
    db.session.add(record)
    db.session.commit()
    return jsonify({"data": {"sync_token": record.sync_token, "device": serialize_device(device)}}), 201
