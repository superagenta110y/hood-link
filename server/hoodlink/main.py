import logging
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response

from hoodlink.bridge import bridge
from hoodlink.config import settings
from hoodlink.models import StatusResponse
from hoodlink.routes import account, market, trading
from hoodlink.ws import client
from hoodlink.ws.robinhood import stream as rh_stream
from hoodlink.ws.stream import router as stream_router

_UI_HTML = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")
_LOGO_SVG = (Path(__file__).parent / "logo.svg").read_bytes()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("HoodLink server starting on %s:%d", settings.host, settings.port)
    print(f"  API key : {settings.api_key}", file=sys.stderr, flush=True)
    print( "  Set HOODLINK_API_KEY or use --api-key to change\n", file=sys.stderr, flush=True)

    if settings.open_browser:
        def _open() -> None:
            try:
                webbrowser.open(f"http://{settings.host}:{settings.port}/", new=2)
            except Exception:
                logger.exception("Failed to open browser")

        threading.Timer(0.8, _open).start()

    yield

    await rh_stream.stop()


app = FastAPI(title="HoodLink", version="0.4.0", lifespan=lifespan)

# Bridge WebSocket (no API key — extension connects over localhost)
@app.websocket("/bridge")
async def bridge_ws(ws: WebSocket):
    await bridge.handle_extension(ws)


# REST routes
app.include_router(market.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")

# Client WebSocket
app.include_router(client.router)

# Robinhood dxFeed stream
app.include_router(stream_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    return _UI_HTML


@app.get("/setup", response_class=HTMLResponse, include_in_schema=False)
async def setup_ui():
    return _UI_HTML


@app.get("/logo.svg", include_in_schema=False)
async def logo():
    return Response(content=_LOGO_SVG, media_type="image/svg+xml")


@app.get("/api/v1/status", tags=["status"])
async def status() -> StatusResponse:
    return StatusResponse(status="ok", bridge_connected=bridge.connected)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
