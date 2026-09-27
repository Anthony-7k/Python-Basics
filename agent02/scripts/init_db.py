from app.config import get_settings
from scripts.migrate import upgrade_database


def main() -> None:
    upgrade_database(get_settings().database_url)
    print("Database schema is at the latest Alembic revision")


if __name__ == "__main__":
    main()
