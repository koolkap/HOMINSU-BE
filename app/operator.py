from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from .auth import current_user, operator_required
from .errors import error_response
from .extensions import db
from .models import DeviceAction, DeviceSync, VenueDevice, utcnow


bp = Blueprint("operator", __name__)
ALLOWED_ACTIONS = {"launch_content", "stop_content", "wake", "sleep", "reboot", "update", "refresh_catalog"}


def serialize_device(device: VenueDevice) -> dict:
    return {
        "id": device.id, "device_key": device.device_key, "name": device.name,
        "headset_model": device.headset_model, "status": device.status,
        "firmware_version": device.app_version, "battery_level": device.battery_level,
        "ip_address": device.ip_address,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "venue": {"id": device.venue.id, "code": device.venue.code, "name": device.venue.name},
    }


@bp.get("/operator/devices")
@operator_required
def devices():
    items = db.session.scalars(
        db.select(VenueDevice).options(joinedload(VenueDevice.venue)).order_by(VenueDevice.name)
    ).all()
    return jsonify({"data": [serialize_device(item) for item in items]})


@bp.post("/operator/devices/actions")
@operator_required
def create_action():
    body = request.get_json(silent=True) or {}
    device_ids = body.get("device_ids")
    action_name = body.get("action")
    payload = body.get("payload", {})
    if not isinstance(device_ids, list) or not device_ids or not all(isinstance(item, int) for item in device_ids):
        return error_response("validation_error", "device_ids must be a non-empty array of integers.", 400)
    if action_name not in ALLOWED_ACTIONS or not isinstance(payload, dict):
        return error_response("validation_error", "A valid action and object payload are required.", 400)
    devices = db.session.scalars(db.select(VenueDevice).where(VenueDevice.id.in_(set(device_ids)))).all()
    if len(devices) != len(set(device_ids)):
        return error_response("not_found", "One or more devices were not found.", 404)
    actions = [DeviceAction(device=device, action=action_name, payload=payload, requested_by_id=current_user().id) for device in devices]
    db.session.add_all(actions)
    db.session.commit()
    return jsonify({"data": {"accepted": len(actions), "actions": [{"id": action.id, "device_id": action.device_id, "action": action.action, "status": action.status} for action in actions]}}), 201


@bp.post("/operator/sync")
@operator_required
def sync():
    body = request.get_json(silent=True) or {}
    device_ids = body.get("device_ids")
    payload = body.get("payload", {})
    if not isinstance(device_ids, list) or not device_ids or not all(isinstance(item, int) for item in device_ids):
        return error_response("validation_error", "device_ids must be a non-empty array of integers.", 400)
    if not isinstance(payload, dict):
        return error_response("validation_error", "payload must be an object.", 400)
    devices = db.session.scalars(db.select(VenueDevice).where(VenueDevice.id.in_(set(device_ids)))).all()
    if len(devices) != len(set(device_ids)):
        return error_response("not_found", "One or more devices were not found.", 404)
    sync_token = uuid4().hex
    records = [DeviceSync(device=device, sync_token=f"{sync_token}-{device.id}", payload=payload) for device in devices]
    db.session.add_all(records)
    db.session.commit()
    return jsonify({"data": {"sync_token": sync_token, "synced": len(records), "device_ids": [device.id for device in devices]}}), 201
