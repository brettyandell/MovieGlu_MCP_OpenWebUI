"""MovieGlu MCP server.

Exposes the MovieGlu v200 movie/cinema/showtime API as MCP tools so that
Open WebUI (native MCP integration, Streamable HTTP transport) — or any
other MCP client — can fetch real theater showtimes inside a chat session.

Tools (12):
    movies_now_showing, movies_coming_soon, search_movies, movie_details,
    movie_trailers, cinemas_nearby, search_cinemas, cinema_showtimes,
    movie_showtimes, closest_showing, ticket_link, api_status
"""
from __future__ import annotations

import functools
import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import MovieGluClient, MovieGluError

TOOL_NAMES = [
    "movies_now_showing",
    "movies_coming_soon",
    "search_movies",
    "movie_details",
    "movie_trailers",
    "cinemas_nearby",
    "search_cinemas",
    "cinema_showtimes",
    "movie_showtimes",
    "closest_showing",
    "ticket_link",
    "api_status",
]


def create_mcp_server(client: MovieGluClient) -> FastMCP:
    """Build a FastMCP server whose tools all delegate to ``client``."""
    try:
        mcp = FastMCP(
            "MovieGlu",
            instructions=(
                "Real movie, cinema and showtime data from the MovieGlu v200 API "
                "for the configured territory. Every result includes a 'status' "
                "envelope with the API state. When a result has ok=false, read the "
                "error field (and mg_message, when present) and tell the user what "
                "to fix. Prefer movie_details / cinema_showtimes / movie_showtimes "
                "after discovering film_id / cinema_id via the search and list tools."
            ),
            stateless_http=True,
        )
    except TypeError:  # older mcp releases without stateless_http
        mcp = FastMCP("MovieGlu")

    def _payload(d: dict) -> str:
        return json.dumps(d, indent=2, ensure_ascii=False)

    def tool(fn):
        """Register a tool that wraps API errors in a JSON error envelope."""

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                data = fn(*args, **kwargs)
                return _payload({"ok": True, "data": data})
            except MovieGluError as exc:
                return _payload(exc.to_dict())
            except Exception as exc:  # noqa: BLE001 - give the model something actionable
                return _payload(
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                )

        return mcp.tool()(wrapper)

    def _clamp(value: int, low: int, high: int) -> int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            v = low
        return max(low, min(high, v))

    @tool
    def movies_now_showing(limit: int = 10) -> str:
        """List the top films currently in cinemas in the configured territory.

        Results are ordered by number of showtimes in the MovieGlu database.
        Each film carries a film_id — use it with movie_showtimes,
        closest_showing, movie_details or ticket_link.

        Args:
            limit: How many films to return (default 10, max 25).
        """
        return client.films_now_showing(n=_clamp(limit, 1, 25))

    @tool
    def movies_coming_soon(limit: int = 10) -> str:
        """List films coming soon to cinemas, ordered by release date.

        Includes release dates, age ratings and synopses.

        Args:
            limit: How many films to return (default 10, max 15).
        """
        return client.films_coming_soon(n=_clamp(limit, 1, 15))

    @tool
    def search_movies(query: str, limit: int = 5) -> str:
        """Search film titles by name fragment (search-as-you-type).

        Results are ordered by popularity (showtime count) and include
        film_id, release date, duration and age rating.

        Args:
            query: Film title fragment (at least 1 character).
            limit: Max results (default 5, max 25).
        """
        return client.film_live_search(query=query, n=_clamp(limit, 1, 25))

    @tool
    def movie_details(film_id: int, size_category: str = "medium") -> str:
        """Full metadata for one film: synopsis, cast, directors, genres,
        ratings, trailers, images and nationwide show dates.

        Args:
            film_id: MovieGlu numeric film id (from search / listing tools).
            size_category: Image size: small, medium, large, xlarge or
                xxlarge (comma-separated for multiple).
        """
        return client.film_details(film_id, size_category or "medium")

    @tool
    def movie_trailers(film_id: int) -> str:
        """Trailer URLs (with qualities and regions) for one film.

        Args:
            film_id: MovieGlu numeric film id.
        """
        return client.trailers(film_id)

    @tool
    def cinemas_nearby(
        limit: int = 10, lat: Optional[float] = None, lng: Optional[float] = None
    ) -> str:
        """List the cinemas nearest to a location, with addresses and distances.

        lat/lng are optional: when omitted, the configured default location
        (MOVIEGLU_LAT / MOVIEGLU_LNG) is used. Only cinemas with showtimes
        in the next 10 days are returned.

        Args:
            limit: Max cinemas (default 10, max 25).
            lat: Latitude (-90..90).
            lng: Longitude (-180..180).
        """
        return client.cinemas_nearby(n=_clamp(limit, 1, 25), lat=lat, lng=lng)

    @tool
    def search_cinemas(
        query: str,
        limit: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> str:
        """Search cinema names or towns (min 3 characters, search-as-you-type).

        Works best with a geolocation (within 75 miles); without it, results
        are alphabetical. lat/lng fall back to the configured default location.

        Args:
            query: Cinema chain or town name fragment (3+ chars).
            limit: Max results (default 5, max 25).
            lat: Latitude (-90..90), optional.
            lng: Longitude (-180..180), optional.
        """
        return client.cinema_live_search(
            query=query, n=_clamp(limit, 1, 25), lat=lat, lng=lng
        )

    @tool
    def cinema_showtimes(
        cinema_id: int,
        date: Optional[str] = None,
        film_id: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> str:
        """All showtimes at one cinema for one date.

        With film_id: only that film. Without: every film playing that day.
        Times are as published by the cinema; times after midnight belong to
        the previous day (cinema day = 03:00-02:59).

        Args:
            cinema_id: MovieGlu numeric cinema id.
            date: YYYY-MM-DD (defaults to today).
            film_id: Optional film id to narrow the schedule to one film.
            sort: popularity or alphabetical.
        """
        return client.cinema_showtimes(
            cinema_id=cinema_id, date=date, film_id=film_id, sort=sort
        )

    @tool
    def movie_showtimes(
        film_id: int,
        date: Optional[str] = None,
        limit: int = 10,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> str:
        """Showtimes for one film at the cinemas nearest a location,
        sorted by distance.

        A location is required: pass lat/lng, or set a default location
        (MOVIEGLU_LAT / MOVIEGLU_LNG).

        Args:
            film_id: MovieGlu numeric film id.
            date: YYYY-MM-DD (defaults to today).
            limit: Max cinemas (default 10, max 25).
            lat: Latitude (-90..90), optional.
            lng: Longitude (-180..180), optional.
        """
        return client.film_showtimes(
            film_id=film_id, date=date, n=_clamp(limit, 1, 25), lat=lat, lng=lng
        )

    @tool
    def closest_showing(
        film_id: int,
        limit: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> str:
        """Nearest cinemas showing a film, regardless of date and time.

        For 'where can I see this film at all?' A location is required
        (lat/lng, or the configured default location).

        Args:
            film_id: MovieGlu numeric film id.
            limit: Max cinemas (default 5, max 20).
            lat: Latitude (-90..90), optional.
            lng: Longitude (-180..180), optional.
        """
        return client.closest_showing(
            film_id=film_id, n=_clamp(limit, 1, 20), lat=lat, lng=lng
        )

    @tool
    def ticket_link(cinema_id: int, film_id: int, date: str, time: str) -> str:
        """Deep link to the cinema's ticketing page with film, date and time
        pre-selected. Use after presenting a showtime to the user.

        MovieGlu does not support seat selection or payment; the link goes
        to the cinema's own website.

        Args:
            cinema_id: MovieGlu numeric cinema id.
            film_id: MovieGlu numeric film id.
            date: Showtime date YYYY-MM-DD.
            time: Showtime time HH:MM (24h) exactly as published.
        """
        return client.purchase_confirmation(
            cinema_id=cinema_id, film_id=film_id, date=date, time=time
        )

    @tool
    def api_status() -> str:
        """Diagnose the MovieGlu connection: which credentials are present,
        and whether a live API call succeeds. Use when other tools fail."""
        config_view = {
            "base_url": client.base_url,
            "territory": client.territory,
            "api_key_set": bool(client.api_key),
            "client_set": bool(client.client_name),
            "authorization_set": bool(client.authorization),
            "default_location_set": bool(
                client.default_lat is not None and client.default_lng is not None
            ),
        }
        try:
            data = client.ping()
            return _payload(
                {
                    "ok": True,
                    "config": config_view,
                    "status": data.get("status"),
                    "message": "MovieGlu connection OK.",
                }
            )
        except MovieGluError as exc:
            return _payload(
                {
                    "ok": False,
                    "config": config_view,
                    "error": str(exc),
                    "status_code": exc.status_code,
                    "mg_message": exc.mg_message,
                }
            )

    return mcp
