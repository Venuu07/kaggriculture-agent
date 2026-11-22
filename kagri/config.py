"""Load kagri/config.yaml once."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Return the project configuration as a dict."""
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
