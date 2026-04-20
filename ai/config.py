"""Centralized environment loading for the AI layer.

Importing :mod:`ai.config` (or calling :func:`load_env`) reads variables from
a ``.env`` file in the project root into ``os.environ``. Values already set in
the real environment take precedence, so CI secrets and shell exports always
win.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

_LOADED = False


def load_env(path: Optional[Path] = None) -> None:
    """Load ``.env`` into ``os.environ`` if present. Safe to call multiple times."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    env_path = path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        logging.getLogger("pawpal.ai.config").warning(
            "python-dotenv not installed; skipping .env load. "
            "Install with `pip install python-dotenv` or `pip install -r requirements.txt`."
        )
        return

    # override=False so a real shell env var beats the .env file
    load_dotenv(env_path, override=False)


def configure_logging() -> None:
    """Apply PAWPAL_LOG_LEVEL (default INFO) to the ``pawpal`` logger tree."""
    level_name = os.environ.get("PAWPAL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.getLogger("pawpal").setLevel(level)


# Auto-load on import so anything that touches `os.environ["HF_TOKEN"]` sees
# the value regardless of which entry point (CLI, Streamlit, pytest) ran first.
load_env()
configure_logging()
