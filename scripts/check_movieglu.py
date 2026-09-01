"""Verify MovieGlu credentials + connectivity without MCP.

Usage (from the project root):
    python scripts/check_movieglu.py

Reads credentials from the environment or a .env file in the project
root (copy .env.example to .env and fill it in). Exits 0 when a live
API call succeeds, 1 otherwise.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from movieglu_mcp.client import MovieGluClient, MovieGluError  # noqa: E402
from movieglu_mcp.config import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(
        dotenv_path=str(pathlib.Path(__file__).resolve().parents[1] / ".env")
    )
    client = MovieGluClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        client_name=settings.client_name,
        authorization=settings.authorization,
        territory=settings.territory,
        default_lat=settings.default_lat,
        default_lng=settings.default_lng,
        timeout=settings.timeout,
    )
    print(f"MovieGlu check: {client.base_url} (territory {client.territory})")
    print(
        "credentials: api_key="
        f"{'set' if client.api_key else 'MISSING'} client="
        f"{'set' if client.client_name else 'MISSING'} authorization="
        f"{'set' if client.authorization else 'MISSING'}"
    )
    try:
        data = client.ping()
    except MovieGluError as exc:
        print(f"FAIL - {exc}")
        if exc.mg_message:
            print(f"MG-message: {exc.mg_message}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL - network error: {exc}")
        return 1

    status = data.get("status") or {}
    print(
        f"OK - state={status.get('state')} count={status.get('count')} "
        f"territory={status.get('territory')} version={status.get('version')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
