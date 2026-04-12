import os

import pytest


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://user:pass@localhost:5432/ntangible_marketing_test",
)
os.environ.setdefault("API_KEY", "test-secret-key")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
os.environ.setdefault("AZURE_OPENAI_MODEL", "gpt-5.4-nano")
os.environ.setdefault("X_PUBLISHER", "mock")
os.environ.setdefault("LINKEDIN_PUBLISHER", "mock")
os.environ.setdefault("LINKEDIN_ACCESS_TOKEN", "test-linkedin-token")
os.environ.setdefault("LINKEDIN_ORGANIZATION_URN", "urn:li:organization:123456")
os.environ.setdefault("LINKEDIN_API_VERSION", "202504")
os.environ.setdefault("INSTAGRAM_PUBLISHER", "mock")
os.environ.setdefault("INSTAGRAM_ACCESS_TOKEN", "test-instagram-token")
os.environ.setdefault("INSTAGRAM_BUSINESS_ACCOUNT_ID", "17841400000000000")
os.environ.setdefault("INSTAGRAM_GRAPH_API_VERSION", "v23.0")
os.environ.setdefault("NEWSLETTER_PUBLISHER", "mock")
os.environ.setdefault("NEWSLETTER_DEFAULT_FROM_NAME", "NTangible")
os.environ.setdefault("NEWSLETTER_REPLY_TO_EMAIL", "team@ntangible.test")
os.environ.setdefault("NEWSLETTER_COACHES_LIST_ID", "aud-coaches")
os.environ.setdefault("NEWSLETTER_PARTNERS_LIST_ID", "aud-partners")
os.environ.setdefault("MAILCHIMP_API_KEY", "mc-test-us1")
os.environ.setdefault("MAILCHIMP_SERVER_PREFIX", "us1")
os.environ.setdefault("CANVA_RENDERER", "mock")
os.environ.setdefault("CANVA_API_KEY", "test-canva-key")
os.environ.setdefault("CANVA_BRAND_TEMPLATE_SET", "default")
os.environ.setdefault("RENDERED_ASSET_ROOT", "data/rendered_assets_test")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-2_test")
os.environ.setdefault("COGNITO_CLIENT_ID", "test-cognito-client")
os.environ.setdefault("COGNITO_CLIENT_SECRET", "test-cognito-secret")
os.environ.setdefault("COGNITO_DOMAIN", "test.auth.us-east-2.amazoncognito.com")
os.environ.setdefault("COGNITO_REDIRECT_URI", "https://test.example.com/control-room/auth/callback")


@pytest.fixture(autouse=True)
def clear_caches():
    try:
        from app.config import (
            get_approved_claims,
            get_brand_voice,
            get_content_pillars,
            get_platform_config,
            get_settings,
        )
    except ModuleNotFoundError:
        yield
        return

    get_settings.cache_clear()
    get_brand_voice.cache_clear()
    get_content_pillars.cache_clear()
    get_approved_claims.cache_clear()
    get_platform_config.cache_clear()
    yield
    get_settings.cache_clear()
    get_brand_voice.cache_clear()
    get_content_pillars.cache_clear()
    get_approved_claims.cache_clear()
    get_platform_config.cache_clear()
