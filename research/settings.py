from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

_CONFIG_PATH = ROOT / "research" / "config.toml"


def load_config() -> dict:
    with _CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)
