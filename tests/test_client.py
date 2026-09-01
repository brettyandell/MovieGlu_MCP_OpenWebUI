"""Tests for the MovieGlu client (no network; requests is mocked).

Run from the project root:
    python -m pytest tests -q
"""
from __future__ import annotations

import json
import pathlib
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from movieglu_mcp.client import MovieGluClient, MovieGluError  # noqa: E402


def make_client(**overrides) -> MovieGluClient:
    defaults = dict(
        api_key="test-key",
        client_name="test-client",
        authorization="Basic TESTTOKEN",
        territory="uk",
        default_lat=51.5,
        default_lng=-0.13,
    )
    defaults.update(overrides)
    return MovieGluClient(**defaults)


def make_response(status_code: int = 200, json_data=None, headers=None) -> mock.Mock:
    resp = mock.Mock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data if json_data is not None else {"status": {"state": "OK"}}
    return resp


def test_required_headers_are_built():
    c = make_client()
    headers = c._headers("51.50;-0.13")
    assert headers["client"] == "test-client"
    assert headers["x-api-key"] == "test-key"
    assert headers["authorization"] == "Basic TESTTOKEN"
    assert headers["territory"] == "UK"  # normalized to uppercase
    assert headers["api-version"] == "v200"
    assert headers["geolocation"] == "51.50;-0.13"
    # device-datetime must be ISO 8601 without a timezone offset
    assert "T" in headers["device-datetime"]
    assert not headers["device-datetime"].endswith("Z")


def test_geolocation_uses_semicolon_and_six_decimals():
    c = make_client(default_lat=51.1234567, default_lng=-0.9876543)
    assert c._geolocation(None, None) == "51.123457;-0.987654"
    # per-call values override the defaults
    assert c._geolocation(2.0, 3.0) == "2.000000;3.000000"
    # no default, no call value -> None
    c2 = make_client(default_lat=None, default_lng=None)
    assert c2._geolocation(None, None) is None


def test_films_now_showing_sends_params():
    c = make_client()
    with mock.patch("movieglu_mcp.client.requests.get", return_value=make_response()) as g:
        c.films_now_showing(n=7)
        _, kwargs = g.call_args
        assert kwargs["params"] == {"n": 7}
        assert g.call_args.args[0].endswith("/filmsNowShowing/")


def test_cinema_showtimes_defaults_date_and_optional_film():
    c = make_client()
    with mock.patch("movieglu_mcp.client.requests.get", return_value=make_response()) as g:
        c.cinema_showtimes(cinema_id=8941, film_id=227902)
        params = g.call_args.kwargs["params"]
        assert params["cinema_id"] == 8941
        assert params["film_id"] == 227902
        assert "date" in params and len(params["date"]) == 10  # today, YYYY-MM-DD

        c.cinema_showtimes(cinema_id=8941)
        params = g.call_args.kwargs["params"]
        assert "film_id" not in params  # all films at the cinema


def test_geo_requiring_tools_fail_without_any_location():
    c = make_client(default_lat=None, default_lng=None)
    with pytest.raises(MovieGluError, match="requires a geolocation"):
        c.cinemas_nearby(n=5)
    with pytest.raises(MovieGluError, match="requires a geolocation"):
        c.film_showtimes(film_id=1)
    with pytest.raises(MovieGluError, match="requires a geolocation"):
        c.closest_showing(film_id=1)


def test_geo_requiring_tools_use_default_location_when_available():
    c = make_client()
    with mock.patch("movieglu_mcp.client.requests.get", return_value=make_response()) as g:
        c.cinemas_nearby(n=5)
        assert g.call_args.kwargs["headers"]["geolocation"] == "51.500000;-0.130000"


def test_missing_credentials_raise_helpful_error():
    c = make_client(api_key="", client_name="", authorization="")
    with pytest.raises(MovieGluError, match="Missing MovieGlu credentials"):
        c.films_now_showing()


def test_http_errors_are_mapped():
    c = make_client()
    with mock.patch("movieglu_mcp.client.requests.get",
                    return_value=make_response(401, headers={"MG-message": "bad key"})):
        with pytest.raises(MovieGluError, match="Authorization failed"):
            c.films_now_showing()

    with mock.patch("movieglu_mcp.client.requests.get",
                    return_value=make_response(429)):
        with pytest.raises(MovieGluError, match="quota exceeded"):
            c.films_now_showing()

    with mock.patch("movieglu_mcp.client.requests.get",
                    return_value=make_response(204, json_data=None)):
        with pytest.raises(MovieGluError, match="No content"):
            c.films_now_showing()


def test_api_level_error_state_is_raised():
    c = make_client()
    body = {"status": {"state": "Error", "message": "Unknown film id"}}
    with mock.patch("movieglu_mcp.client.requests.get",
                    return_value=make_response(200, json_data=body)):
        with pytest.raises(MovieGluError, match="Unknown film id"):
            c.film_details(film_id=999)


def test_cinema_live_search_min_query_length():
    c = make_client()
    with pytest.raises(MovieGluError, match="at least 3 characters"):
        c.cinema_live_search(query="od")


def test_error_envelope_shape():
    exc = MovieGluError("boom", status_code=429, mg_message="quota")
    envelope = exc.to_dict()
    assert envelope["ok"] is False
    assert json.loads(json.dumps(envelope))["error"] == "boom"
    assert envelope["status_code"] == 429
    assert envelope["mg_message"] == "quota"


# ---------------------------------------------------------------------- #
# MCP server (skipped automatically when the 'mcp' package is absent)
# ---------------------------------------------------------------------- #
fastmcp = pytest.importorskip("mcp.server.fastmcp")


def _server_tools():
    from movieglu_mcp.server import create_mcp_server

    mcp = create_mcp_server(make_client())
    manager = mcp._tool_manager  # FastMCP internal, stable across 1.x
    tools = manager._tools if isinstance(manager._tools, dict) else {
        t.name: t for t in manager.list_tools()
    }
    return mcp, tools


def test_all_expected_tools_are_registered():
    from movieglu_mcp.server import TOOL_NAMES

    _, tools = _server_tools()
    registered = set(tools.keys())
    assert set(TOOL_NAMES) <= registered


def test_tools_return_json_error_envelope_on_missing_credentials():
    from movieglu_mcp.server import create_mcp_server

    empty = MovieGluClient()  # no credentials at all
    mcp = create_mcp_server(empty)
    fn = mcp._tool_manager._tools["movies_now_showing"]
    fn = getattr(fn, "fn", fn)  # newer SDKs wrap the raw callable
    result = json.loads(fn(limit=1))
    assert result["ok"] is False
    assert "Missing MovieGlu credentials" in result["error"]


def test_tool_success_envelope_shape(monkeypatch):
    from movieglu_mcp.server import create_mcp_server

    c = make_client()
    mcp = create_mcp_server(c)
    monkeypatch.setattr(
        c, "films_now_showing", lambda n: {"films": [], "status": {"state": "OK"}}
    )
    fn = mcp._tool_manager._tools["movies_now_showing"]
    fn = getattr(fn, "fn", fn)
    result = json.loads(fn(limit=3))
    assert result["ok"] is True
    assert result["data"]["status"]["state"] == "OK"
