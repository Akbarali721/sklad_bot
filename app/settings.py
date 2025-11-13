from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_SECRET: str = "dev-secret"
    ADMIN_TG_IDS: str = ""
    class Config:
        env_file = ".env"

settings = Settings()
