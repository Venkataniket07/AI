import os

from utils.logger import get_app_logger


def load_dotenv(dotenv_path: str) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ without overriding existing variables."""
    if not os.path.exists(dotenv_path):
        return
    logger = get_app_logger()
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        logger.error("Could not read %s", dotenv_path, exc_info=True)
        return

    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.warning("Ignoring malformed line %d in %s", lineno, dotenv_path)
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        elif " #" in val:  # strip inline comment on unquoted values
            val = val.split(" #", 1)[0].strip()
        if key and key not in os.environ:
            os.environ[key] = val
