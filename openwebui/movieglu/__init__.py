"""
title: MovieGlu
author: The Grid
version: 0.2.0
description: Real movies, cinemas and theater showtimes from the MovieGlu v200 API — now showing, coming soon, search, showtimes, ticket links.
requirements: requests
"""
# MovieGlu tool for Open WebUI — real movies, cinemas and theater showtimes
# from the MovieGlu v200 API (https://developer.movieglu.com/).
#
# IMPORT VIA THE WEB INTERFACE:
#   Admin Panel -> Tools -> Create
#   ID: movieglu  (alphanumeric/underscore)
#   Paste this entire file into the code editor -> Save
#   Then click the gear icon (Valves) and fill in your MovieGlu credentials
#   from the "Your MovieGlu API access credentials" email:
#     api_key, client, authorization (full "Basic ..." value), territory.
#
# CONVENTION NOTE (Open WebUI 0.9.x): the tool class must be named `Tools`
# with nested `Valves`/`UserValves` models, a zero-argument __init__, and
# plain async methods (there is no @function_tool decorator in this version).
# Saving a tool actually loads it: if the code fails to load, the create
# request is rejected and nothing is stored.
#
# This file is fully self-contained: no local imports. It mirrors the MCP
# server in src/movieglu_mcp and the drop-in folder in openwebui/movieglu/.

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Dict, Optional

import requests
from pydantic import BaseModel, Field


class MovieGluError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        mg_message: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.mg_message = mg_message


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _today() -> str:
    return dt.date.today().isoformat()


class Tools:
    class Valves(BaseModel):
        """Admin configuration (gear icon under Admin Panel -> Tools -> MovieGlu).

        Values come from the MovieGlu credentials email. 'authorization' is the
        FULL value of the Authorization header, typically starting with "Basic ".
        """

        base_url: str = "https://api-gate2.movieglu.com/"
        api_key: str = Field(
            default="",
            description="MovieGlu x-api-key (from the credentials email)",
        )
        client: str = Field(
            default="",
            description="MovieGlu client username (from the credentials email)",
        )
        authorization: str = Field(
            default="",
            description='Full Authorization header value, e.g. "Basic A1B2c3..."',
        )
        territory: str = Field(
            default="US",
            description="Two-letter ISO territory you licensed (US, UK, CA, ...)",
        )
        default_lat: str = Field(
            default="",
            description="Default latitude (-90..90); used when a tool call omits lat",
        )
        default_lng: str = Field(
            default="",
            description="Default longitude (-180..180); used when a tool call omits lng",
        )
        timeout: float = Field(default=30.0, description="HTTP timeout in seconds")

    class UserValves(BaseModel):
        """Per-user settings (none needed yet)."""

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    # Internal MovieGlu plumbing
    # ------------------------------------------------------------------ #
    def _geolocation(self, lat=None, lng=None) -> Optional[str]:
        """Per-call lat/lng win over the configured default; MovieGlu wants 'lat;lng'."""
        lat = _as_float(lat if lat is not None else self.valves.default_lat)
        lng = _as_float(lng if lng is not None else self.valves.default_lng)
        if lat is None or lng is None:
            return None
        return f"{lat:.6f};{lng:.6f}"

    def _headers(self, geolocation: Optional[str]) -> Dict[str, str]:
        return {
            "client": self.valves.client,
            "x-api-key": self.valves.api_key,
            "authorization": self.valves.authorization,
            "territory": self.valves.territory.upper(),
            "api-version": "v200",
            # ISO 8601 without timezone offset: yyyy-mm-ddThh:mm:ss.sss
            "device-datetime": dt.datetime.now().isoformat(timespec="milliseconds"),
            **({"geolocation": geolocation} if geolocation else {}),
        }

    def _get(
        self,
        resource: str,
        params: Optional[Dict[str, object]] = None,
        geolocation: Optional[str] = None,
        require_geo: bool = False,
    ) -> Dict[str, object]:
        missing = [
            name
            for name, value in (
                ("api_key", self.valves.api_key),
                ("client", self.valves.client),
                ("authorization", self.valves.authorization),
            )
            if not value
        ]
        if missing:
            raise MovieGluError(
                "Missing MovieGlu credentials: "
                + ", ".join(missing)
                + ". Set them in the MovieGlu tool settings (Valves) under the "
                "Admin Panel before calling MovieGlu tools."
            )
        if require_geo and not geolocation:
            raise MovieGluError(
                f"'{resource}' requires a location. Pass lat/lng with the "
                "tool call, or set default_lat/default_lng in the MovieGlu "
                "tool settings."
            )
        url = f"{self.valves.base_url.rstrip('/')}/{resource}/"
        resp = self.session.get(
            url,
            params=params,
            headers=self._headers(geolocation),
            timeout=self.valves.timeout,
        )
        mg_message = resp.headers.get("MG-message")
        if resp.status_code == 204:
            raise MovieGluError(
                "No content (HTTP 204): the location may be outside the "
                "licensed territory, or no data exists for this combination."
                + (f" MG-message: {mg_message}" if mg_message else ""),
                status_code=204,
                mg_message=mg_message,
            )
        if resp.status_code == 429:
            raise MovieGluError(
                "Request quota exceeded (HTTP 429): MovieGlu evaluation "
                "(75 requests) or sandbox (10,000 requests) limit reached.",
                status_code=429,
                mg_message=mg_message,
            )
        if resp.status_code in (401, 403):
            raise MovieGluError(
                f"Authorization failed (HTTP {resp.status_code}): check the "
                "api_key, client, authorization and territory values in the "
                "tool settings.",
                status_code=resp.status_code,
                mg_message=mg_message,
            )
        if resp.status_code >= 400:
            raise MovieGluError(
                f"HTTP {resp.status_code} from '{resource}'"
                + (f": {mg_message}" if mg_message else ""),
                status_code=resp.status_code,
                mg_message=mg_message,
            )
        try:
            data: Dict[str, object] = resp.json()
        except ValueError:
            raise MovieGluError(f"'{resource}' returned a non-JSON response.")
        status = data.get("status") or {}
        if status.get("state") == "Error":
            raise MovieGluError(
                f"MovieGlu error in '{resource}': {status.get('message')}",
                status_code=resp.status_code,
                mg_message=mg_message,
            )
        return data

    def _call(self, resource: str, params=None, geolocation=None, require_geo=False):
        """Wrap an API call in a uniform ok/error envelope for the model."""
        try:
            return {
                "ok": True,
                "data": self._get(resource, params, geolocation, require_geo),
            }
        except MovieGluError as exc:
            return {
                "ok": False,
                "error": str(exc),
                "status_code": exc.status_code,
                "mg_message": exc.mg_message,
            }
        except requests.RequestException as exc:
            return {"ok": False, "error": f"Network error calling MovieGlu: {exc}"}

    @staticmethod
    def _clamp(value, low: int, high: int) -> int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            v = low
        return max(low, min(high, v))

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #
    async def movies_now_showing(self, limit: int = 10) -> dict:
        """List the top films currently in cinemas in the configured territory.

        Ordered by number of showtimes. Each film carries a film_id to use
        with movie_showtimes, closest_showing, movie_details or ticket_link.
        """
        return await asyncio.to_thread(
            self._call, "filmsNowShowing", {"n": self._clamp(limit, 1, 25)}
        )

    async def movies_coming_soon(self, limit: int = 10) -> dict:
        """List films coming soon to cinemas, ordered by release date.

        Includes release dates, age ratings and synopses.
        """
        return await asyncio.to_thread(
            self._call, "filmsComingSoon", {"n": self._clamp(limit, 1, 15)}
        )

    async def search_movies(self, query: str, limit: int = 5) -> dict:
        """Search film titles by name fragment (search-as-you-type).

        Results are ordered by popularity and include film_id, release date,
        duration and age rating.
        """
        query = (query or "").strip()
        if not query:
            return {"ok": False, "error": "search_movies needs a non-empty query."}
        return await asyncio.to_thread(
            self._call,
            "filmLiveSearch",
            {"query": query, "n": self._clamp(limit, 1, 25)},
        )

    async def movie_details(
        self, film_id: int, size_category: str = "medium"
    ) -> dict:
        """Full metadata for one film: synopsis, cast, directors, genres,
        ratings, trailers, images and nationwide show dates.

        size_category: small, medium, large, xlarge or xxlarge.
        """
        params: Dict[str, object] = {"film_id": film_id}
        if size_category:
            params["size_category"] = size_category
        return await asyncio.to_thread(self._call, "filmDetails", params)

    async def movie_trailers(self, film_id: int) -> dict:
        """Trailer URLs (with qualities and regions) for one film."""
        return await asyncio.to_thread(self._call, "trailers", {"film_id": film_id})

    async def cinemas_nearby(
        self,
        limit: int = 10,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """List the cinemas nearest to a location, with addresses and distances.

        lat/lng are optional: when omitted, the tool's configured default
        location (default_lat/default_lng) is used. Only cinemas with
        showtimes in the next 10 days are returned.
        """
        return await asyncio.to_thread(
            self._call,
            "cinemasNearby",
            {"n": self._clamp(limit, 1, 25)},
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    async def search_cinemas(
        self,
        query: str,
        limit: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """Search cinema names or towns (minimum 3 characters).

        Works best with a geolocation (within 75 miles); without it, results
        are alphabetical. lat/lng fall back to the configured default location.
        """
        query = (query or "").strip()
        if len(query) < 3:
            return {
                "ok": False,
                "error": "search_cinemas needs a query of at least 3 characters.",
            }
        return await asyncio.to_thread(
            self._call,
            "cinemaLiveSearch",
            {"query": query, "n": self._clamp(limit, 1, 25)},
            geolocation=self._geolocation(lat, lng),
        )

    async def cinema_showtimes(
        self,
        cinema_id: int,
        date: Optional[str] = None,
        film_id: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> dict:
        """All showtimes at one cinema for one date.

        With film_id: only that film. Without: every film playing that day.
        date is YYYY-MM-DD (defaults to today). sort: popularity or
        alphabetical. Times are as published by the cinema; showtimes after
        midnight belong to the previous day.
        """
        params: Dict[str, object] = {"cinema_id": cinema_id, "date": date or _today()}
        if film_id is not None:
            params["film_id"] = film_id
        if sort:
            params["sort"] = sort
        return await asyncio.to_thread(self._call, "cinemaShowTimes", params)

    async def movie_showtimes(
        self,
        film_id: int,
        date: Optional[str] = None,
        limit: int = 10,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """Showtimes for one film at the cinemas nearest a location,
        sorted by distance. A location is required: pass lat/lng or rely on
        the configured default location.
        """
        params: Dict[str, object] = {
            "film_id": film_id,
            "date": date or _today(),
            "n": self._clamp(limit, 1, 25),
        }
        return await asyncio.to_thread(
            self._call,
            "filmShowTimes",
            params,
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    async def closest_showing(
        self,
        film_id: int,
        limit: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """Nearest cinemas showing a film, regardless of date and time
        ('where can I see this film at all?'). A location is required:
        lat/lng or the configured default location.
        """
        return await asyncio.to_thread(
            self._call,
            "closestShowing",
            {"film_id": film_id, "n": self._clamp(limit, 1, 20)},
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    async def ticket_link(
        self, cinema_id: int, film_id: int, date: str, time: str
    ) -> dict:
        """Deep link to the cinema's ticketing page with film, date and time
        pre-selected. Use after presenting a showtime to the user. MovieGlu
        does not support seat selection or payment; the link opens the
        cinema's own website.
        """
        return await asyncio.to_thread(
            self._call,
            "purchaseConfirmation",
            {
                "cinema_id": cinema_id,
                "film_id": film_id,
                "date": date,
                "time": time,
            },
        )

    async def api_status(self) -> dict:
        """Diagnose the MovieGlu connection: which credentials are set, and
        whether a live API call succeeds. Use when other MovieGlu tools fail.
        """
        config_view = {
            "base_url": self.valves.base_url,
            "territory": self.valves.territory.upper(),
            "api_key_set": bool(self.valves.api_key),
            "client_set": bool(self.valves.client),
            "authorization_set": bool(self.valves.authorization),
            "default_location_set": bool(
                _as_float(self.valves.default_lat) is not None
                and _as_float(self.valves.default_lng) is not None
            ),
        }
        try:
            data = await asyncio.to_thread(self._get, "filmsNowShowing", {"n": 1})
            return {
                "ok": True,
                "config": config_view,
                "status": data.get("status"),
                "message": "MovieGlu connection OK.",
            }
        except MovieGluError as exc:
            return {
                "ok": False,
                "config": config_view,
                "error": str(exc),
                "status_code": exc.status_code,
                "mg_message": exc.mg_message,
            }
        except requests.RequestException as exc:
            return {
                "ok": False,
                "config": config_view,
                "error": f"Network error: {exc}",
            }
