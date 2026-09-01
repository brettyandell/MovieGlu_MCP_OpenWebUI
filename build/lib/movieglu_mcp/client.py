"""Client for the MovieGlu v200 REST API.

Pure-Python client (no MCP dependency) shared by the MCP server, the
standalone check script and (in self-contained form) the OpenWebUI
custom tool.

MovieGlu API reference: https://developer.movieglu.com/
 - Base URL:      https://api-gate2.movieglu.com/  (trailing slash matters)
 - Auth headers: client, x-api-key, authorization (full Basic value),
                 territory, api-version (v200)
 - device-datetime: ISO 8601 WITHOUT timezone offset, e.g. 2026-08-31T14:00:00.000
 - geolocation header format: "lat;lng"  (semicolon, up to 6 decimals)

Quirks encoded here:
 - Geolocation is separated by a SEMICOLON, not a comma.
 - The cinema "day" runs 03:00-02:59; showtimes after midnight belong to
   the previous calendar day (do not "fix" returned times).
 - device-datetime must be current or you can get empty 204 responses.
 - 204 = no content (often geolocation outside the licensed territory).
 - 429 = evaluation/sandbox request quota exceeded.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional

import requests

DEFAULT_BASE_URL = "https://api-gate2.movieglu.com/"
API_VERSION = "v200"


class MovieGluError(RuntimeError):
    """Raised when the MovieGlu API returns an error or no usable content."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        mg_message: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.mg_message = mg_message

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly error envelope for tool results."""
        return {
            "ok": False,
            "error": str(self),
            "status_code": self.status_code,
            "mg_message": self.mg_message,
        }


def today() -> str:
    """Today's date as YYYY-MM-DD (MovieGlu's cinema-day convention)."""
    return _dt.date.today().isoformat()


class MovieGluClient:
    """Synchronous client for the MovieGlu v200 API (GET resources only)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "",
        client_name: str = "",
        authorization: str = "",
        territory: str = "US",
        default_lat: Optional[float] = None,
        default_lng: Optional[float] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client_name = client_name
        self.authorization = authorization
        self.territory = (territory or "US").upper()
        self.default_lat = default_lat
        self.default_lng = default_lng
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Plumbing
    # ------------------------------------------------------------------ #
    def require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("x-api-key (MOVIEGLU_API_KEY)", self.api_key),
                ("client (MOVIEGLU_CLIENT)", self.client_name),
                ("authorization (MOVIEGLU_AUTHORIZATION)", self.authorization),
            )
            if not value
        ]
        if missing:
            raise MovieGluError(
                "Missing MovieGlu credentials: "
                + ", ".join(missing)
                + ". Set them in .env / OpenWebUI tool settings before calling the API."
            )

    def _geolocation(
        self,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Optional[str]:
        """Resolve geolocation: per-call value wins, else configured default.

        MovieGlu requires the 'lat;lng' header format (semicolon, 6 decimals).
        """
        if lat is None:
            lat = self.default_lat
        if lng is None:
            lng = self.default_lng
        if lat is None or lng is None:
            return None
        return f"{float(lat):.6f};{float(lng):.6f}"

    def _headers(self, geolocation: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "client": self.client_name,
            "x-api-key": self.api_key,
            "authorization": self.authorization,
            "territory": self.territory,
            "api-version": API_VERSION,
            # ISO 8601 without timezone offset: yyyy-mm-ddThh:mm:ss.sss
            "device-datetime": _dt.datetime.now().isoformat(timespec="milliseconds"),
        }
        if geolocation:
            headers["geolocation"] = geolocation
        return headers

    def _get(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        geolocation: Optional[str] = None,
        require_geo: bool = False,
    ) -> Dict[str, Any]:
        self.require_credentials()
        if require_geo and not geolocation:
            raise MovieGluError(
                f"'{resource}' requires a geolocation (lat;lng). Provide lat/lng "
                "with the tool call, or set a default location "
                "(MOVIEGLU_LAT / MOVIEGLU_LNG) in the configuration."
            )
        url = f"{self.base_url}/{resource}/"
        resp = requests.get(
            url,
            params=params,
            headers=self._headers(geolocation),
            timeout=self.timeout,
        )
        mg_message = resp.headers.get("MG-message")

        if resp.status_code == 204:
            detail = (
                " Common causes: the geolocation is outside the licensed "
                "territory, or no data exists for this combination."
            )
            raise MovieGluError(
                f"No content from '{resource}' (HTTP 204).{detail} "
                + (f"MG-message: {mg_message}" if mg_message else "").strip(),
                status_code=204,
                mg_message=mg_message,
            )
        if resp.status_code == 429:
            raise MovieGluError(
                "Request quota exceeded (HTTP 429): the MovieGlu evaluation "
                "(75 requests) or sandbox (10,000 requests) limit was hit. "
                "Retry later or request a production key from MovieGlu.",
                status_code=429,
                mg_message=mg_message,
            )
        if resp.status_code in (401, 403):
            raise MovieGluError(
                f"Authorization failed (HTTP {resp.status_code}): check "
                "x-api-key, client, authorization and territory headers "
                "against your MovieGlu credentials email.",
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
            data: Dict[str, Any] = resp.json()
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

    # ------------------------------------------------------------------ #
    # Resources
    # ------------------------------------------------------------------ #
    def ping(self) -> Dict[str, Any]:
        """Smallest possible call, used to verify connectivity + credentials."""
        return self._get("filmsNowShowing", {"n": 1})

    def films_now_showing(self, n: int = 10) -> Dict[str, Any]:
        """Top films now showing, ordered by number of showtimes (max 25)."""
        return self._get("filmsNowShowing", {"n": n})

    def films_coming_soon(self, n: int = 10) -> Dict[str, Any]:
        """Films coming soon, ordered by release date (max 15)."""
        return self._get("filmsComingSoon", {"n": n})

    def film_live_search(self, query: str, n: int = 5) -> Dict[str, Any]:
        """Live film title search (search-as-you-type), max 25."""
        query = (query or "").strip()
        if not query:
            raise MovieGluError("filmLiveSearch needs a non-empty query string.")
        return self._get("filmLiveSearch", {"query": query, "n": n})

    def film_details(
        self,
        film_id: int,
        size_category: str = "medium",
    ) -> Dict[str, Any]:
        """Metadata, cast, synopsis, images and trailers for one film.

        size_category: small|medium|large|xlarge|xxlarge (comma-separated ok).
        """
        params: Dict[str, Any] = {"film_id": film_id}
        if size_category:
            params["size_category"] = size_category
        return self._get("filmDetails", params)

    def trailers(self, film_id: int) -> Dict[str, Any]:
        """Trailer URLs for one film."""
        return self._get("trailers", {"film_id": film_id})

    def cinemas_nearby(
        self,
        n: int = 10,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Nearest cinemas to a geolocation (max 25). Geolocation mandatory."""
        return self._get(
            "cinemasNearby",
            {"n": n},
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    def cinema_live_search(
        self,
        query: str,
        n: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Live cinema name search (min 3 chars), works best with geolocation."""
        query = (query or "").strip()
        if len(query) < 3:
            raise MovieGluError(
                "cinemaLiveSearch requires a query of at least 3 characters."
            )
        return self._get(
            "cinemaLiveSearch",
            {"query": query, "n": n},
            geolocation=self._geolocation(lat, lng),
        )

    def cinema_details(
        self,
        cinema_id: int,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Address, phone, coordinates and show dates for one cinema."""
        return self._get(
            "cinemaDetails",
            {"cinema_id": cinema_id},
            geolocation=self._geolocation(lat, lng),
        )

    def cinema_showtimes(
        self,
        cinema_id: int,
        date: Optional[str] = None,
        film_id: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Showtimes at one cinema for one date (all films, or a single film).

        date: YYYY-MM-DD (defaults to today). sort: popularity|alphabetical.
        Omitting film_id returns showtimes for ALL films at that cinema.
        """
        params: Dict[str, Any] = {"cinema_id": cinema_id, "date": date or today()}
        if film_id is not None:
            params["film_id"] = film_id
        if sort:
            params["sort"] = sort
        return self._get("cinemaShowTimes", params)

    def film_showtimes(
        self,
        film_id: int,
        date: Optional[str] = None,
        n: int = 10,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Showtimes for one film at cinemas near a geolocation (max 25).

        Results are sorted by distance; distance needs the geolocation header.
        """
        params: Dict[str, Any] = {"film_id": film_id, "date": date or today(), "n": n}
        return self._get(
            "filmShowTimes",
            params,
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    def closest_showing(
        self,
        film_id: int,
        n: int = 5,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Nearest cinemas showing a film, regardless of date (max 20).

        Geolocation mandatory.
        """
        params: Dict[str, Any] = {"film_id": film_id, "n": n}
        return self._get(
            "closestShowing",
            params,
            geolocation=self._geolocation(lat, lng),
            require_geo=True,
        )

    def purchase_confirmation(
        self,
        cinema_id: int,
        film_id: int,
        date: str,
        time: str,
    ) -> Dict[str, Any]:
        """Deep link to the cinema's ticket page with film/date/time pre-selected.

        date: YYYY-MM-DD, time: HH:MM (24h) as published by the cinema.
        MovieGlu does not support seat selection or payment.
        """
        return self._get(
            "purchaseConfirmation",
            {
                "cinema_id": cinema_id,
                "film_id": film_id,
                "date": date,
                "time": time,
            },
        )
