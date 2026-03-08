from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://cdnuser:cdnpass@postgres:5432/cdndb"

    # S3 / MinIO
    s3_endpoint_url: str = "http://minio:9000"
    s3_bucket_name: str = "cdn-assets"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin"
    aws_region: str = "us-east-1"

    # CDN
    cdn_enabled: bool = False
    cdn_secret: str = "change-me"
    cloudfront_distribution_id: str = "XXXXXXXXXXXXXXXXX"

    # Origin Shield
    origin_shield_enabled: bool = False

    # Access Token TTL in seconds
    token_ttl_seconds: int = 3600


settings = Settings()
