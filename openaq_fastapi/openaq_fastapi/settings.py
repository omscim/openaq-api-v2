from pydantic import BaseSettings
from pathlib import Path
from os import environ


class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_WRITE_URL: str
    OPENAQ_ENV: str = "staging"
    OPENAQ_FASTAPI_URL: str
    TESTLOCAL: bool = True
    OPENAQ_FETCH_BUCKET: str
    OPENAQ_ETL_BUCKET: str
    OPENAQ_CACHE_TIMEOUT: int = 900
    LOG_LEVEL: str = 'INFO'

    class Config:
        parent = Path(__file__).resolve().parent.parent.parent
        if 'DOTENV' in environ:
            env_file = Path.joinpath(parent, environ['DOTENV'])
        else:
            env_file = Path.joinpath(parent, ".env")


settings = Settings()
