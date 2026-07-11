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

    return jsonify({"data": {
        "bucket": bucket_name,
        "path": object_path,
        "url": public_url,
        "original_name": filename,
        "content_type": content_type,
        "size": len(payload),
        "provider": provider,
    }}), 201
