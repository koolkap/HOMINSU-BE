import os
from datetime import timedelta


database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu",
)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)


class Config:
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "unsafe-development-only-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        if origin.strip()
    ]
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "hominsu")
    S3_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("S3_ENDPOINT_URL")
    S3_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    S3_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    S3_BUCKET = os.getenv("S3_BUCKET", SUPABASE_STORAGE_BUCKET)
    STORAGE_MAX_FILE_SIZE = int(os.getenv("STORAGE_MAX_FILE_SIZE", str(50 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = STORAGE_MAX_FILE_SIZE + 1024 * 1024
    JSON_SORT_KEYS = False
