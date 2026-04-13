from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    api_key: str
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_model: str = "gpt-5.4-nano"
    control_room_require_auth: bool = False
    control_room_default_timezone: str = "America/Toronto"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: str = ""
    cognito_domain: str = ""
    cognito_redirect_uri: str = ""
    content_brain_storage_root: str = "data/content_brain"
    rendered_asset_root: str = "data/rendered_assets"
    x_publisher: str = "mock"
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_twikit_username: str = ""
    x_twikit_password: str = ""
    x_twikit_email: str = ""
    linkedin_publisher: str = "mock"
    linkedin_access_token: str = ""
    linkedin_organization_urn: str = ""
    linkedin_api_version: str = "202504"
    instagram_publisher: str = "mock"
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_graph_api_version: str = "v23.0"
    newsletter_publisher: str = "mock"
    newsletter_default_from_name: str = "NTangible"
    newsletter_reply_to_email: str = ""
    newsletter_coaches_list_id: str = ""
    newsletter_partners_list_id: str = ""
    mailchimp_api_key: str = ""
    mailchimp_server_prefix: str = ""
    canva_renderer: str = "mock"
    canva_api_key: str = ""
    canva_brand_template_set: str = "default"
    image_renderer: str = "pillow"
    generated_asset_root: str = "storage/generated_assets"
    google_client_id: str = ""
    google_client_secret: str = ""

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


@lru_cache
def get_canva_templates() -> dict:
    return load_yaml("canva_templates.yaml")


@lru_cache
def get_brand_palette() -> dict:
    return load_yaml("brand_palette.yaml")


def get_canva_template(platform: str, template_family: str) -> dict | None:
    """Look up a Canva template config by platform and template family name.

    Returns ``None`` when no match is found.  The returned dict contains
    ``template_id`` and ``data_fields`` keys.
    """
    templates = get_canva_templates().get("templates", {})
    platform_templates = templates.get(platform, {})
    return platform_templates.get(template_family)
