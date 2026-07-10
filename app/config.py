import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "unsafe-development-only-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        if origin.strip()
    ]
    JSON_SORT_KEYS = False
