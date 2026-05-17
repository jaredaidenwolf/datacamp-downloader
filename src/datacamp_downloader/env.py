import os
from pathlib import Path
from typing import Optional


def load_env() -> None:
    """Load .env from the current working directory when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.cwd() / ".env")


def get_token_from_env() -> Optional[str]:
    for key in ("TOKEN", "DATACAMP_TOKEN", "DCT"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    return None
