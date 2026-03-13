"""WebSocket endpoint -- proxies Robinhood dxFeed stream to API clients.

Connect: ws://127.0.0.1:7878/api/v1/stream?api_key=<key>

Client -> server messages:
  {"action":"subscribe","subscriptions":[{"symbol":"AAPL","type":"Trade"},{"symbol":"AAPL","type":"Quote"}]}
  {"action":"subscribe","subscriptions":[{"symbol":"AAPL","type":"Candle","from_time":1234567890000,"instrument_type":"equity"}]}
  {"action":"unsubscribe","subscriptions":[{"symbol":"AAPL","type":"Trade"}]}

Server -> client messages:
  {"type":"rh_status","connected":bool,"subscriptions":[...]}  — on connect + on state change
  {"type":"subscribed","symbol":"AAPL","eventType":"Trade"}
  {"type":"error","message":"..."}
  {"eventType":"Trade","eventSymbol":"AAPL","price":150.0,"dayVolume":1234567,"time":1773344599807}
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from hoodlink.auth import require_api_key, require_api_key_ws
from hoodlink.bridge import bridge
from hoodlink.ws.robinhood import stream

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/stream/status")
async def stream_status(_key: str = Depends(require_api_key)):
    return JSONResponse({
        "connected": stream.running,
        "subscriptions": stream.subscriptions,
    })


@router.websocket("/api/v1/stream")
async def market_stream(ws: WebSocket, _key: str = Depends(require_api_key_ws)):
    await ws.accept()
    queue = stream.add_subscriber()
    forward_task = asyncio.create_task(_forward(ws, queue))

    # Send current state immediately so the client can sync
    await ws.send_text(json.dumps({
        "type": "rh_status",
        "connected": stream.running,
        "subscriptions": stream.subscriptions,
    }))

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "subscribe":
                if not stream.running:
                    try:
                        stream_token = await bridge.fetch_streaming_token()
                        await stream.start(stream_token)
                        # Broadcast updated status to all subscribers (via fan_out)
                        stream._fan_out({"type": "rh_status", "connected": True, "subscriptions": stream.subscriptions})
                    except RuntimeError as e:
                        await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
                        continue

                for sub in msg.get("subscriptions", []):
                    symbol = sub.get("symbol", "").strip()
                    event_type = sub.get("type", "").strip()
                    extra = {k: v for k, v in sub.items() if k not in ("symbol", "type")}
                    if symbol and event_type:
                        try:
                            await stream.subscribe(symbol, event_type, **extra)
                            await ws.send_text(json.dumps({
                                "type": "subscribed",
                                "symbol": symbol,
                                "eventType": event_type,
                            }))
                        except Exception as e:
                            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

            elif action == "unsubscribe":
                for sub in msg.get("subscriptions", []):
                    symbol = sub.get("symbol", "").strip()
                    event_type = sub.get("type", "").strip()
                    if symbol and event_type:
                        await stream.unsubscribe(symbol, event_type)
                        await ws.send_text(json.dumps({
                            "type": "unsubscribed",
                            "symbol": symbol,
                            "eventType": event_type,
                        }))

    except WebSocketDisconnect:
        logger.info("Stream client disconnected")
    except Exception:
        logger.exception("Stream WS error")
    finally:
        stream.remove_subscriber(queue)
        forward_task.cancel()


async def _forward(ws: WebSocket, queue: asyncio.Queue) -> None:
    try:
        while True:
            event = await queue.get()
            # Enrich rh_status events with current subscription list
            if event.get("type") == "rh_status":
                event = {**event, "subscriptions": stream.subscriptions}
            await ws.send_text(json.dumps(event))
    except (WebSocketDisconnect, Exception):
        pass
