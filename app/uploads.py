from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from storage3.exceptions import StorageApiError
from supabase import create_client
from werkzeug.utils import secure_filename

from .auth import current_user, operator_required
from .errors import error_response


bp = Blueprint("uploads", __name__)

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
    bucket_name = current_app.config["SUPABASE_STORAGE_BUCKET"]
    object_path = f"uploads/{user.id}/{uuid4().hex}{suffix}"

    try:
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
    except StorageConfigurationError:
        current_app.logger.error("Supabase storage credentials are not configured")
        return error_response("storage_unavailable", "Media storage is not configured.", 503)
    except StorageApiError as error:
        current_app.logger.exception("Supabase storage upload failed", exc_info=error)
        return error_response("storage_error", "The file could not be stored.", 502)

    return jsonify({"data": {
        "bucket": bucket_name,
        "path": object_path,
        "url": public_url,
        "original_name": filename,
        "content_type": content_type,
        "size": len(payload),
    }}), 201
