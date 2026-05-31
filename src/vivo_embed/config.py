"""Konfiguracio betolto — config.yaml + .env"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

def load() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["google"]["api_key"] = os.environ.get("GOOGLE_API_KEY", "")
    return cfg

_cfg: dict | None = None

def get() -> dict:
    global _cfg
    if _cfg is None:
        _cfg = load()
    return _cfg
