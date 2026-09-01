# MovieGlu MCP

Real **theater showtimes, films, cinemas and ticket deep links** from the
[MovieGlu API](https://developer.movieglu.com/), exposed to **Open WebUI
chat sessions** as tools.

Two interchangeable integrations, one shared client:

| Path | What it is | When to use |
| --- | --- | --- |
| `openwebui/movieglu_tool.py` | **Single-file OpenWebUI tool** | Fastest path: paste into the web UI (`Admin Panel → Tools → Create`). No file access needed. |
| `src/movieglu_mcp/` | **MCP server** (stdio + Streamable HTTP) | OpenWebUI's native MCP integration: `Settings → Admin → Integrations → External Tool Servers → Type: MCP (Streamable HTTP)`. Also works with any other MCP client. |
| `openwebui/movieglu/` | **Drop-in tool folder** (same code) | Prefer installing by file into the container: `components/tools/tools/movieglu/`. |

`openwebui/movieglu_tool.py` and `openwebui/movieglu/__init__.py` are
byte-identical by design — one canonical tool, two delivery forms.

Open WebUI only speaks **Streamable HTTP** for MCP (no stdio/SSE natively),
so the server ships an HTTP transport; a stdio transport is included for
local testing and for the `mcpo` bridge if you ever need it.

---

## 1. Get MovieGlu credentials

1. Request an API key at <https://developer.movieglu.com/request-key/> and
   pick a territory (the evaluation key is limited to that country).
2. You receive an email with:
   - `client` (username)
   - `x-api-key`
   - `authorization` (a full Basic-auth value, e.g. `Basic A1B2c3...`)
   - evaluation credentials (**75 requests**) + sandbox credentials
     (**10,000 requests**)
3. `HTTP 429` means the quota for that credential set is exhausted.

## 2. Configure

Copy `.env.example` to `.env` and fill in:

```
MOVIEGLU_API_KEY=...
MOVIEGLU_CLIENT=...
MOVIEGLU_AUTHORIZATION=Basic ...
MOVIEGLU_TERRITORY=US
MOVIEGLU_LAT=37.7749      # optional default location
MOVIEGLU_LNG=-122.4194    # optional default location
```

For the **custom tool**, the same values are set in
`Admin Panel → Tools → MovieGlu → ⚙️ (Valves)` — or pre-filled in
`openwebui/movieglu/config.yaml`.

## 3. Run the MCP server

```bash
pip install .            # installs movieglu-mcp + its dependencies

# Streamable HTTP (what OpenWebUI connects to), default port 8000
movieglu-mcp --transport http --port 8000
# endpoint:  http://0.0.0.0:8000/mcp

# stdio (local MCP clients / mcpo bridge)
movieglu-mcp --transport stdio
```

(Alternatively run without installing: `set PYTHONPATH=src` /
`export PYTHONPATH=src`, then `python -m movieglu_mcp ...`.)

Docker (same behavior, credentials via `--env-file .env`):

```bash
docker build -t movieglu-mcp .
docker run --env-file .env -p 8000:8000 movieglu-mcp
```

### Connect to Open WebUI

1. `Settings → Admin → Integrations → External Tool Servers → + Add Connection`
2. **Type: MCP (Streamable HTTP)**
3. **URL:**
   - server on the host, OpenWebUI in Docker: `http://host.docker.internal:8000/mcp`
   - both on the same Docker network: `http://movieglu-mcp:8000/mcp`
   - same machine / published port: `http://<ip>:8000/mcp`
4. **Auth: None** (credentials live server-side in the .env, not in OpenWebUI)
5. Save, restart Open WebUI if prompted.
6. In a chat: `+ → Integrations → Tools → MovieGlu` (enable once per chat
   for the model to use the tools).

### Import the single-file tool through the web interface (recommended)

1. Open `openwebui/movieglu_tool.py` in this project — it is fully
   self-contained (frontmatter metadata, credentials UI, client and all 12
   tools in one file, no local imports).
2. In Open WebUI: **Admin Panel → Tools → Create**
   - **ID:** `movieglu`
   - **Name:** `MovieGlu`
   - **Description:** `Real movies, cinemas and theater showtimes from the MovieGlu API`
3. Paste the entire file contents into the code editor → **Save**.
   (Equivalent path: **Import From Link** with a URL to the file, e.g. a
   raw GitHub link.)

   > **v0.9.2 note (Monolith build):** saving a tool actually *loads* it
   > first. If the code fails to load (wrong class name, missing import,
   > etc.) the request fails and **nothing is stored** — the tool will not
   > appear in the list even though the dialog closed. This file follows
   > the v0.9.2 contract: `class Tools` with nested `Valves`/`UserValves`,
   > zero-arg `__init__`, plain `async` methods, no `@function_tool`.
   > If a save “succeeds” but the tool never lists, that is the cause.
4. Open the **⚙️ gear icon (Valves)** next to the tool and fill in the
   credentials from your MovieGlu email: `api_key`, `client`,
   `authorization` (the full `Basic ...` value), `territory`, and an
   optional default `default_lat` / `default_lng`.
5. In a chat: `+ → Integrations → Tools → MovieGlu` (enable per chat, or
   set as a default tool on a model).

The `requirements: requests` frontmatter line makes Open WebUI
auto-install `requests` on first load
(`ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` is on by default).

### Alternative: install the drop-in folder (older OpenWebUI builds)

```bash
# inside an OpenWebUI container: copy the whole folder to
/app/backend/open_webui/components/tools/tools/movieglu/
```

> **Not available in v0.9.x (Monolith build):** that `components/tools`
> directory does not exist there; tools are DB-stored and created through the
> Admin Panel (or `POST /api/v1/tools/create`). The folder is kept for
> compatibility with older builds. Restart Open WebUI, then set the
> credentials under `Admin Panel → Tools → MovieGlu` (same Valves).
> `config.yaml` pre-fills defaults; `requirements.txt` covers `requests`.

## 4. Tools (12, identical in both integrations)

| Tool | MovieGlu resource | Notes |
| --- | --- | --- |
| `movies_now_showing(limit)` | `filmsNowShowing` | top films by showtime count |
| `movies_coming_soon(limit)` | `filmsComingSoon` | by release date |
| `search_movies(query, limit)` | `filmLiveSearch` | returns `film_id`s |
| `movie_details(film_id, size_category)` | `filmDetails` | synopsis, cast, ratings |
| `movie_trailers(film_id)` | `trailers` | trailer URLs |
| `cinemas_nearby(limit, lat, lng)` | `cinemasNearby` | geolocation required |
| `search_cinemas(query, limit, lat, lng)` | `cinemaLiveSearch` | min 3-char query |
| `cinema_showtimes(cinema_id, date, film_id, sort)` | `cinemaShowTimes` | omit `film_id` for the whole cinema schedule |
| `movie_showtimes(film_id, date, limit, lat, lng)` | `filmShowTimes` | by distance; geolocation required |
| `closest_showing(film_id, limit, lat, lng)` | `closestShowing` | nearest cinema, any date |
| `ticket_link(cinema_id, film_id, date, time)` | `purchaseConfirmation` | deep link to ticketing page |
| `api_status()` | `filmsNowShowing` (n=1) | credential/connectivity diagnostics |

Typical chat flow: `search_movies` → `movie_showtimes` → present times →
`ticket_link` for the chosen showing.

All tools return a uniform envelope:

```json
{ "ok": true,  "data": { ...MovieGlu payload incl. status envelope... } }
{ "ok": false, "error": "...", "status_code": 401, "mg_message": "..." }
```

so the model gets an actionable message instead of a crash.

## 5. MovieGlu quirks baked into the code

- **Geolocation header uses a semicolon:** `51.510391;-0.13013` (max 6 decimals).
- **Cinema day runs 03:00–02:59** — post-midnight showtimes belong to the
  previous calendar day; never "fix" returned times.
- **`device-datetime` must be current** (`yyyy-mm-ddThh:mm:ss.sss`, no TZ
  offset) — it's regenerated on every request, and a stale one yields 204s.
- **HTTP 204** = no content (usually geolocation outside the licensed
  territory or no data); **429** = quota exhausted; the `MG-message`
  response header is surfaced in every error.
- Resource names are **case-sensitive** (`cinemaShowTimes`, not `CinemaDetails`-style).
- `filmShowTimes` / `cinemasNearby` / `closestShowing` **require** a
  geolocation; without lat/lng the configured default location is used, and
  the error envelope tells you exactly what to set if there isn't one.

## 6. Verify

```bash
python scripts/check_movieglu.py     # live ping with your .env creds
python -m pytest tests -q           # offline unit tests (mocked requests)
```

## 7. Repository layout

```
MovieGlu MCP/
├── pyproject.toml            # package + movieglu-mcp console script
├── requirements.txt          # mcp, requests, python-dotenv
├── requirements-dev.txt      # + pytest
├── Dockerfile                # Streamable HTTP image
├── .env.example              # credential/transport config template
├── src/movieglu_mcp/
│   ├── client.py             # MovieGlu v200 REST client (no MCP deps)
│   ├── config.py             # env/.env -> Settings
│   ├── server.py             # FastMCP server, 12 tools
│   └── __main__.py           # python -m movieglu_mcp [--transport ...]
├── openwebui/
│   ├── movieglu_tool.py      # SINGLE FILE for the web UI (Tools > Create)
│   └── movieglu/            # drop-in folder variant (same code + metadata)
│       ├── __init__.py      # byte-identical to movieglu_tool.py
│       ├── manifest.yaml
│       ├── config.yaml      # default Valve values
│       └── requirements.txt
├── scripts/check_movieglu.py # credential/connectivity gate
└── tests/test_client.py      # mocked-request unit tests
```
