from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Story Pattern Lab"
    app_env: str = "local"
    database_url: str = "sqlite:///./storylab.db"
    collector_user_agent: str = "StoryPatternLabBot/0.1"
    ai_analysis_min_viral_score: int = 70
    ai_analysis_daily_limit: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
