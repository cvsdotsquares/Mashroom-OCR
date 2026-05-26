"""
Application configuration — one class per environment.
Load order: env var FLASK_ENV → selects class → config_map lookup in create_app().
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


class Config:
    """Base config shared by all environments."""

    # Security
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024          # 50 MB
    ALLOWED_EXTENSIONS = {
        "pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"
    }

    # OCR templates file
    TEMPLATES_JSON_PATH = BASE_DIR / "templates.json"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/mashroom_ocr"
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    @classmethod
    def validate(cls) -> None:
        """Call at startup to assert all required env vars are present."""
        missing = [
            v for v in ("FLASK_SECRET_KEY", "DATABASE_URL", "ANTHROPIC_API_KEY")
            if not os.environ.get(v)
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required env vars for production: {', '.join(missing)}"
            )


class TestingConfig(Config):
    TESTING = True
    DEBUG   = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED        = False


# Registry used by create_app()
config_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}
