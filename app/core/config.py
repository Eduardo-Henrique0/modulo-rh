from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./rh.db"
    JWT_SECRET: str = "troque-este-secret-em-producao"
    JWT_ALGORITHM: str = "HS256"
    CORE_URL: str = "http://localhost:8000"
    PORT: int = 8002

    class Config:
        env_file = ".env"


settings = Settings()
