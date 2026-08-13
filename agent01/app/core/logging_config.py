import logging
import sys


LOG_FORMAT = (
    "%(asctime)s "
    "%(levelname)s "
    "%(name)s "
    "%(message)s"
)


def setup_logging(
    level: int = logging.INFO,
):
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )

    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )

    logging.getLogger("httpcore").setLevel(
        logging.WARNING
    )


def get_logger(name: str):
    return logging.getLogger(name)