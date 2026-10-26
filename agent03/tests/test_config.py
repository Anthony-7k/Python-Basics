import pytest

from app.config import DEFAULT_SECRET, Settings


def test_allowed_origins_are_split():
    settings = Settings(allowed_origins="https://one.example, https://two.example")
    assert settings.allowed_origin_list == ["https://one.example", "https://two.example"]


def test_production_rejects_default_secret():
    settings = Settings(app_env="production", secret_key=DEFAULT_SECRET)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        settings.validate_runtime()


def test_production_rejects_fake_security_and_eager_queue():
    settings = Settings(
        app_env="production",
        secret_key="a-secure-production-secret-with-at-least-32-bytes",
        virus_scanner_backend="fake",
        task_queue_backend="eager",
    )
    with pytest.raises(ValueError, match="virus scanner"):
        settings.validate_runtime()

    settings.virus_scanner_backend = "clamav"
    with pytest.raises(ValueError, match="Eager task queue"):
        settings.validate_runtime()

