import os
import logging
from datetime import datetime

_app_logger = None
_ai_logger = None

def init_loggers():
    global _app_logger, _ai_logger
    
    # 1. Create .log directory in the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, ".log")
    os.makedirs(log_dir, exist_ok=True)
    
    # 2. Generate timestamp: YYYYMMDD_HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    app_log_file = os.path.join(log_dir, f"app_{timestamp}.log")
    ai_log_file = os.path.join(log_dir, f"ai_{timestamp}.log")
    
    # 3. Read log levels from environment
    app_level_str = os.environ.get("APP_LOG_LEVEL", "INFO").strip().upper()
    ai_level_str = os.environ.get("AI_LOG_LEVEL", "DEBUG").strip().upper()
    
    app_level = getattr(logging, app_level_str, logging.INFO)
    ai_level = getattr(logging, ai_level_str, logging.DEBUG)
    
    # 4. Formatter
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    # Configure App Logger
    _app_logger = logging.getLogger("app")
    _app_logger.setLevel(app_level)
    _app_logger.propagate = False
    
    if _app_logger.handlers:
        for handler in list(_app_logger.handlers):
            _app_logger.removeHandler(handler)
            
    app_handler = logging.FileHandler(app_log_file, encoding="utf-8")
    app_handler.setFormatter(formatter)
    _app_logger.addHandler(app_handler)
    
    # Configure AI Logger
    _ai_logger = logging.getLogger("ai")
    _ai_logger.setLevel(ai_level)
    _ai_logger.propagate = False
    
    if _ai_logger.handlers:
        for handler in list(_ai_logger.handlers):
            _ai_logger.removeHandler(handler)
            
    ai_handler = logging.FileHandler(ai_log_file, encoding="utf-8")
    ai_handler.setFormatter(formatter)
    _ai_logger.addHandler(ai_handler)

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
