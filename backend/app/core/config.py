"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Application
    APP_NAME: str = "Virtual Environment Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/virtualenv_db"
    MONGODB_URL: str = "mongodb://localhost:27017/virtualenv_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 7200
    
    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "virtualenv-storage"
    S3_BUCKET_VIDEOS: str = "virtualenv-videos"
    S3_BUCKET_SCENES: str = "virtualenv-scenes"
    S3_BUCKET_DATASETS: str = "virtualenv-datasets"
    
    # Google Cloud
    GCP_PROJECT_ID: Optional[str] = None
    GCP_BUCKET_NAME: str = "virtualenv-storage"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4096
    
    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    
    # ElevenLabs
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: str = "noreply@virtualenv.ai"
    EMAILS_FROM_NAME: str = "Virtual Environment Platform"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000"
    ]
    
    # Processing
    MAX_VIDEO_SIZE_MB: int = 5000
    MAX_VIDEO_DURATION_SECONDS: int = 7200
    SUPPORTED_VIDEO_FORMATS: List[str] = ["mp4", "mov", "avi", "mkv"]
    FRAME_EXTRACTION_FPS: int = 30
    NERF_TRAINING_ITERATIONS: int = 30000
    GAUSSIAN_SPLATTING_ITERATIONS: int = 30000
    
    # GPU
    CUDA_VISIBLE_DEVICES: str = "0"
    TORCH_CUDA_ARCH_LIST: str = "8.0;8.6;8.9"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_PORT: int = 9090
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Feature Flags
    ENABLE_VOICE_CLONING: bool = True
    ENABLE_AI_CHAT: bool = True
    ENABLE_DATASET_MARKETPLACE: bool = True
    ENABLE_VR_STREAMING: bool = True
    
    # Subscription Tiers
    FREE_TIER_PROJECTS: int = 3
    FREE_TIER_STORAGE_GB: int = 10
    BASIC_TIER_PROJECTS: int = 10
    BASIC_TIER_STORAGE_GB: int = 100
    PRO_TIER_PROJECTS: int = 50
    PRO_TIER_STORAGE_GB: int = 500
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    return Settings()


# Global settings instance
settings = get_settings()

# Made with Bob
