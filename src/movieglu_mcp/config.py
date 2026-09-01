"""Environment-based configuration for the MovieGlu MCP server."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:  # python-dotenv is optional; env vars always work without it
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover
    _load_dotenv = None


@dataclass
class Settings:
    base_url: str
    api_key: str
    client_name: str
    authorization: str
    territory: str
    default_lat: Optional[float]
    default_lng: Optional[float]
    timeout: float


def _env_float(name: str) -> Optional[float]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def load_settings(dotenv_path: Optional[str] = None) -> Settings:
    """Read settings from the environment (and a .env file when available).

    A .env file is loaded from the current working directory (or the
    explicit path given) before env vars are read; real environment
    variables always win over .env values.
    """
    if _load_dotenv is not None:
        if dotenv_path:
            _load_dotenv(dotenv_path, override=False)
        else:
            _load_dotenv(override=False)

    return Settings(
        base_url=os.getenv("MOVIEGLU_BASE_URL", "https://api-gate2.movieglu.com/"),
        api_key=os.getenv("MOVIEGLU_API_KEY", ""),
        client_name=os.getenv("MOVIEGLU_CLIENT", ""),
        authorization=os.getenv("MOVIEGLU_AUTHORIZATION", ""),
        territory=os.getenv("MOVIEGLU_TERRITORY", "US"),
        default_lat=_env_float("MOVIEGLU_LAT"),
        default_lng=_env_float("MOVIEGLU_LNG"),
        timeout=float(os.getenv("MOVIEGLU_TIMEOUT", "30")),
    )
