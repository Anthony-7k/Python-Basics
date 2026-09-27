from __future__ import annotations

import os

from app.config import get_settings
from scripts.migrate import upgrade_database


def main() -> None:
    settings = get_settings()
    upgrade_database(settings.database_url)
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(settings.api_port),
        ],
    )


if __name__ == "__main__":
    main()
