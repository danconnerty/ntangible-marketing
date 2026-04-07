from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    api_key: str
    anthropic_api_key: str
    x_publisher: str = "mock"
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_twikit_username: str = ""
    x_twikit_password: str = ""
    x_twikit_email: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


CONFIG_DIR = Path(__file__).parent / "config_data"


def load_yaml(filename: str) -> dict:
    with (CONFIG_DIR / filename).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache
def get_brand_voice() -> dict:
    return load_yaml("brand_voice.yaml")


@lru_cache
def get_content_pillars() -> dict:
    return load_yaml("content_pillars.yaml")


@lru_cache
def get_approved_claims() -> dict:
    return load_yaml("approved_claims.yaml")


@lru_cache
def get_platform_config(platform: str = "x") -> dict:
    return load_yaml(f"platforms/{platform}.yaml")
