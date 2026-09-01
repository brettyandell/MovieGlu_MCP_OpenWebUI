"""Entry point:  python -m movieglu_mcp [--transport stdio|http] ...

Transports:
    stdio   - for local MCP clients and the mcpo bridge
    http    - Streamable HTTP; the transport Open WebUI's native MCP
              integration (Settings > Admin > Integrations > External Tool
              Servers > Type: MCP (Streamable HTTP)) connects to.
"""
from __future__ import annotations

import argparse
import os


def main() -> None:
    from .client import MovieGluClient
    from .config import load_settings
    from .server import create_mcp_server

    settings = load_settings()
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
    mcp = create_mcp_server(client)

    parser = argparse.ArgumentParser(
        prog="movieglu-mcp",
        description="MovieGlu MCP server (movies, cinemas, showtimes)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MOVIEGLU_MCP_TRANSPORT", "stdio"),
        help="MCP transport (default from MOVIEGLU_MCP_TRANSPORT or stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MOVIEGLU_MCP_HOST", "0.0.0.0"),
        help="Bind address for the HTTP transport",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MOVIEGLU_MCP_PORT", "8000")),
        help="Port for the HTTP transport",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MOVIEGLU_MCP_PATH", "/mcp"),
        help="URL path for the Streamable HTTP endpoint",
    )
    args = parser.parse_args()

    if args.transport == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = args.path
        print(
            f"MovieGlu MCP: Streamable HTTP on "
            f"http://{args.host}:{args.port}{args.path}"
        )
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
