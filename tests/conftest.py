import os

import pytest


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://user:pass@localhost:5432/ntangible_marketing_test",
)
os.environ.setdefault("API_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("X_PUBLISHER", "mock")


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
