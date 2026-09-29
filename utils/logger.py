import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_app_logger = None
_ai_logger = None

MAX_LOG_BYTES = 1_000_000  # rotate each log at ~1 MB
LOG_BACKUPS = 5            # keep app.log plus 5 older files (app.log.1 ... app.log.5)

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _configure(name: str, path: str, level: int) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):  # re-initialising must not stack handlers
        logger.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    return logger


def init_loggers(log_dir: Optional[str] = None):
    """
    Log to <project>/.log/app.log and ai.log, rotating at ~1 MB with a bounded number of backups.
    Levels come from APP_LOG_LEVEL (default INFO) and AI_LOG_LEVEL (default DEBUG).
    """
    global _app_logger, _ai_logger

    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".log")
    os.makedirs(log_dir, exist_ok=True)

    app_level = getattr(logging, os.environ.get("APP_LOG_LEVEL", "INFO").strip().upper(), logging.INFO)
    ai_level = getattr(logging, os.environ.get("AI_LOG_LEVEL", "DEBUG").strip().upper(), logging.DEBUG)

    _app_logger = _configure("app", os.path.join(log_dir, "app.log"), app_level)
    _ai_logger = _configure("ai", os.path.join(log_dir, "ai.log"), ai_level)


def get_app_logger():
    global _app_logger
    if _app_logger is None:
        _app_logger = logging.getLogger("app")
    return _app_logger


def get_ai_logger():
    global _ai_logger
    if _ai_logger is None:
        _ai_logger = logging.getLogger("ai")
    return _ai_logger
