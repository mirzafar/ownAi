from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ownai"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    openai_api_key: str = ""
    openai_transcribe_model: str = "gpt-4o-transcribe"
    openai_analysis_model: str = "gpt-4o-mini"

    cors_origins: str = "http://localhost:5173"

    bitrix_webhook_url: str = ""


settings = Settings()
