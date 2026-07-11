import logging
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, current_app, jsonify, request
from storage3.exceptions import StorageApiError
from supabase import create_client
from werkzeug.utils import secure_filename

from .auth import current_user, operator_required
from .errors import error_response
from .extensions import db
from .models import MediaAsset


bp = Blueprint("uploads", __name__)
logger = logging.getLogger("uvicorn.error")

ALLOWED_MEDIA_TYPES = {
    ".jpeg": {"image/jpeg"},
    ".jpg": {"image/jpeg"},
    ".mov": {"video/quicktime"},
    ".mp4": {"video/mp4"},
    ".png": {"image/png"},
    ".webm": {"video/webm"},
    ".webp": {"image/webp"},
}


class StorageConfigurationError(RuntimeError):
    pass


def get_supabase_client():
    client = current_app.extensions.get("supabase")
    if client is not None:
        return client

    url = current_app.config.get("SUPABASE_URL")
    key = current_app.config.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise StorageConfigurationError("Supabase storage credentials are not configured.")

    client = create_client(url, key)
    current_app.extensions["supabase"] = client
    return client


def get_s3_client():
    client = current_app.extensions.get("s3")
    if client is not None:
        return client

    required = {
        "AWS_ENDPOINT_URL_S3": current_app.config.get("S3_ENDPOINT_URL"),
        "AWS_ACCESS_KEY_ID": current_app.config.get("S3_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": current_app.config.get("S3_SECRET_ACCESS_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise StorageConfigurationError(f"Missing S3 variables: {', '.join(missing)}")

    client = boto3.client(
        "s3",
        endpoint_url=current_app.config["S3_ENDPOINT_URL"],
        region_name=current_app.config["S3_REGION"],
        aws_access_key_id=current_app.config["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["S3_SECRET_ACCESS_KEY"],
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    current_app.extensions["s3"] = client
    return client


def storage_provider() -> str:
    configured = current_app.config.get("STORAGE_PROVIDER", "auto")
    if configured not in {"auto", "s3", "supabase"}:
        raise StorageConfigurationError("STORAGE_PROVIDER must be 's3', 'supabase', or 'auto'.")
    if configured != "auto":
        return configured
    if current_app.config.get("S3_ACCESS_KEY_ID") or current_app.config.get("S3_SECRET_ACCESS_KEY"):
        return "s3"
    return "supabase"


def public_storage_url(bucket_name: str, object_path: str) -> str:
    supabase_url = (current_app.config.get("SUPABASE_URL") or "").rstrip("/")
    if not supabase_url:
        endpoint = current_app.config["S3_ENDPOINT_URL"]
        project_ref = endpoint.split("//", 1)[-1].split(".storage.supabase.co", 1)[0]
        supabase_url = f"https://{project_ref}.supabase.co"
    return f"{supabase_url}/storage/v1/object/public/{quote(bucket_name)}/{quote(object_path, safe='/')}"


def delete_storage_object(provider: str, bucket_name: str, object_path: str) -> None:
    if provider == "s3":
        get_s3_client().delete_object(Bucket=bucket_name, Key=object_path)
    else:
        get_supabase_client().storage.from_(bucket_name).remove([object_path])


def serialize_media_asset(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "bucket": asset.bucket,
        "path": asset.object_path,
        "url": asset.public_url,
        "original_name": asset.original_name,
        "title": asset.title,
        "content_type": asset.content_type,
        "media_kind": asset.media_kind,
        "size": asset.size_bytes,
        "size_bytes": asset.size_bytes,
        "provider": asset.provider,
        "is_showcase_ready": asset.is_showcase_ready,
        "storage_state": asset.storage_state,
        "owner": {"id": asset.owner.id, "display_name": asset.owner.display_name},
        "created_at": asset.created_at.isoformat(),
    }


def serialize_showcase_asset(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "title": asset.title,
        "url": asset.public_url,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "created_at": asset.created_at.isoformat(),
    }


@bp.post("/storage/upload")
@operator_required
def upload_file():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return error_response("validation_error", "A media file is required.", 400)

    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    content_type = (uploaded.mimetype or "").lower()
    if not filename or content_type not in ALLOWED_MEDIA_TYPES.get(suffix, set()):
        return error_response(
            "validation_error",
            "Supported formats are JPEG, PNG, WebP, MP4, WebM, and MOV.",
            400,
        )

    max_size = current_app.config["STORAGE_MAX_FILE_SIZE"]
    payload = uploaded.stream.read(max_size + 1)
    if not payload:
        return error_response("validation_error", "The selected file is empty.", 400)
    if len(payload) > max_size:
        return error_response("request_entity_too_large", "Files may not exceed 50 MiB.", 413)

    user = current_user()
    object_path = f"uploads/{user.id}/{uuid4().hex}{suffix}"

    try:
        provider = storage_provider()
        if provider == "s3":
            bucket_name = current_app.config["S3_BUCKET"]
            get_s3_client().put_object(
                Bucket=bucket_name,
                Key=object_path,
                Body=payload,
                ContentType=content_type,
                CacheControl="public, max-age=3600",
            )
            public_url = public_storage_url(bucket_name, object_path)
        else:
            bucket_name = current_app.config["SUPABASE_STORAGE_BUCKET"]
            bucket = get_supabase_client().storage.from_(bucket_name)
            bucket.upload(
                object_path,
                payload,
                file_options={
                    "cache-control": "3600",
                    "content-type": content_type,
                    "upsert": "false",
                },
            )
            public_url = bucket.get_public_url(object_path)
    except StorageConfigurationError as error:
        logger.error("Storage configuration error: %s", error)
        return error_response("storage_unavailable", str(error), 503)
    except (BotoCoreError, ClientError, StorageApiError):
        logger.exception("Storage upload failed")
        return error_response("storage_error", "The file could not be stored.", 502)
    except Exception:
        # Some storage clients raise decoding errors for non-JSON upstream responses.
        logger.exception("Unexpected storage provider response")
        return error_response("storage_error", "The file could not be stored.", 502)

    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename
    asset = MediaAsset(
        owner=user,
        provider=provider,
        bucket=bucket_name,
        object_path=object_path,
        public_url=public_url,
        original_name=filename,
        title=title[:200],
        content_type=content_type,
        media_kind="video" if content_type.startswith("video/") else "image",
        size_bytes=len(payload),
        is_showcase_ready=content_type in {"video/mp4", "video/webm"},
        storage_state="ready",
    )
    try:
        db.session.add(asset)
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            delete_storage_object(provider, bucket_name, object_path)
        except Exception:
            logger.exception("Failed to clean up storage after database error")
        logger.exception("Failed to persist uploaded media")
        return error_response("persistence_error", "The uploaded media could not be recorded.", 500)

    return jsonify({"data": serialize_media_asset(asset)}), 201


@bp.get("/operator/media")
@operator_required
def list_operator_media():
    user = current_user()
    query = db.select(MediaAsset).order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
    if user.role.name != "admin":
        query = query.where(MediaAsset.owner_id == user.id)
    assets = db.session.scalars(query.limit(100)).all()
    return jsonify({"data": [serialize_media_asset(asset) for asset in assets]})


@bp.delete("/operator/media/<int:asset_id>")
@operator_required
def delete_operator_media(asset_id: int):
    user = current_user()
    asset = db.session.get(MediaAsset, asset_id)
    if not asset or (user.role.name != "admin" and asset.owner_id != user.id):
        return error_response("not_found", "Media asset not found.", 404)

    try:
        delete_storage_object(asset.provider, asset.bucket, asset.object_path)
    except Exception:
        asset.is_showcase_ready = False
        asset.storage_state = "cleanup_required"
        db.session.commit()
        logger.exception("Failed to delete media from storage")
        return error_response("storage_error", "The media could not be deleted from storage.", 502)

    db.session.delete(asset)
    db.session.commit()
    return "", 204


@bp.get("/showcase/media")
def list_showcase_media():
    query = (
        db.select(MediaAsset)
        .where(
            MediaAsset.is_showcase_ready.is_(True),
            MediaAsset.storage_state == "ready",
            MediaAsset.media_kind == "video",
        )
        .order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
        .limit(24)
    )
    assets = db.session.scalars(query).all()
    return jsonify({"data": [serialize_showcase_asset(asset) for asset in assets]})
