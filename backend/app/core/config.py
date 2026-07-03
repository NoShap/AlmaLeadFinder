from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables (or .env locally)."""

    database_url: str = "postgresql+psycopg://alma:alma@localhost:5432/alma"

    jwt_secret: str = "dev-secret-change-me-32-bytes-minimum!"
    jwt_expires_minutes: int = 8 * 60

    admin_email: str = "attorney@example.com"
    admin_password: str = "letmein"

    # Email. When resend_api_key is empty, emails are logged to stdout instead of sent,
    # so the app runs end-to-end without any external credentials.
    resend_api_key: str = ""
    email_from: str = "Alma <onboarding@resend.dev>"
    attorney_notification_email: str = "attorney@example.com"

    frontend_origin: str = "http://localhost:3000"

    # Resume storage. When s3_endpoint_url is set, resumes go to S3-compatible object
    # storage (MinIO locally, AWS S3 in production — same code path). When empty,
    # they fall back to local disk under upload_dir.
    s3_endpoint_url: str = ""
    s3_bucket: str = "resumes"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    upload_dir: str = "var/uploads"
    max_resume_bytes: int = 5 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
