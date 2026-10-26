"""Local configuration check only; never contacts a provider or prints secrets."""
from urllib.parse import urlsplit

from app.config import Settings


def check() -> bool:
    settings = Settings()
    missing = [name for name, value in {
        "CLOUD_MODEL_BASE_URL": settings.cloud_model_base_url,
        "CLOUD_MODEL_NAME": settings.cloud_model_name,
        "CLOUD_MODEL_API_KEY": settings.cloud_model_api_key.get_secret_value(),
    }.items() if not value.strip()]
    if missing:
        print("Missing local configuration: " + ", ".join(missing))
        print("No network request was made. Do not send your API key through chat.")
        return False
    settings.extraction_backend = "cloud"
    try:
        settings.validate_runtime()
    except ValueError:
        print("Invalid configuration: use your actual HTTPS API endpoint, not a documentation placeholder.")
        print("No network request was made. Check region/workspace and model settings locally.")
        return False
    print(f"Configuration valid: provider={settings.cloud_model_provider}, "
          f"host={urlsplit(settings.cloud_model_base_url).hostname}, model={settings.cloud_model_name}")
    print("No network request was made; model access and billing are not verified.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if check() else 1)
