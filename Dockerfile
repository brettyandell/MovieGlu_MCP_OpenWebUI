# MovieGlu MCP server (Streamable HTTP by default — the transport OpenWebUI's
# native MCP integration connects to).
#
# Build:
#   docker build -t movieglu-mcp .
# Run (from this folder, with a filled-in .env):
#   docker run --env-file .env -p 8000:8000 movieglu-mcp
#
# Then in OpenWebUI: Settings > Admin > Integrations > External Tool Servers
# > + Add Connection > Type: MCP (Streamable HTTP) > URL: http://<host>:8000/mcp
# If OpenWebUI itself runs in Docker on the same host, use
# http://host.docker.internal:8000/mcp or a shared-docker-network hostname.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY src ./src

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src \
    MOVIEGLU_MCP_TRANSPORT=http \
    MOVIEGLU_MCP_HOST=0.0.0.0 \
    MOVIEGLU_MCP_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "movieglu_mcp"]
