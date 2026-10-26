from app.config import get_settings
from app.database import Database


def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    database.seed_demo(settings)
    print("Demo tenant and user are ready")


if __name__ == "__main__":
    main()

