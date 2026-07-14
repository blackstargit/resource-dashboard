"""
app/core/logging.py
===================
Shared logging configuration. Call setup_logging() once at startup,
then use get_logger(name) throughout the app.
"""
import logging

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger. Safe to call multiple times."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring the root config is applied."""
    setup_logging()
    return logging.getLogger(name)
