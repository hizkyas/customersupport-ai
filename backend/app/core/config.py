import json
from typing import Any, List, Union
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

def parse_cors_origins(v: Any) -> List[str]:
    if isinstance(v, str):
        try:
            val = json.loads(v)
            if isinstance(val, list):
                return [str(item) for item in val]
        except json.JSONDecodeError:
            pass
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list):
        return [str(item) for item in v]
    return []

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str
    REDIS_URL: str

    # Security Configuration
    JWT_SECRET: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # AI Provider Configuration
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = "mock-key"
    LLM_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_API_KEY: str = "mock-key"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # CORS and Network Configurations
    CORS_ORIGINS: Annotated[
        List[str],
        BeforeValidator(parse_cors_origins)
    ] = []

    # Application Settings
    ENVIRONMENT: str = "development"
    MAX_UPLOAD_SIZE_MB: int = 10

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

settings = Settings()
