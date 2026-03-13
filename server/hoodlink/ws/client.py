import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from hoodlink.auth import require_api_key_ws
from hoodlink.bridge import bridge

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def client_websocket(ws: WebSocket, _key: str = Depends(require_api_key_ws)):
    await ws.accept()
    subscriptions: dict[str, asyncio.Queue] = {}
    tasks: list[asyncio.Task] = []

    async def _forward(channel: str, queue: asyncio.Queue):
        try:
            while True:
                data = await queue.get()
                await ws.send_text(json.dumps({"channel": channel, "data": data}))
        except (WebSocketDisconnect, Exception):
            pass

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "subscribe":
                channel = msg.get("channel", "")
                if channel and channel not in subscriptions:
                    queue = bridge.subscribe_stream(channel)
                    subscriptions[channel] = queue
                    task = asyncio.create_task(_forward(channel, queue))
                    tasks.append(task)
                    await ws.send_text(
                        json.dumps({"status": "subscribed", "channel": channel})
                    )

            elif action == "unsubscribe":
                channel = msg.get("channel", "")
                if channel in subscriptions:
                    bridge.unsubscribe_stream(channel, subscriptions.pop(channel))
                    await ws.send_text(
                        json.dumps({"status": "unsubscribed", "channel": channel})
                    )

            elif action == "command":
                try:
                    result = await bridge.send_command(
                        msg.get("method", "GET"),
                        msg.get("url", ""),
                        headers=msg.get("headers"),
                        body=msg.get("body"),
                    )
                    await ws.send_text(
                        json.dumps({"id": msg.get("id"), "data": result})
                    )
                except RuntimeError as e:
                    await ws.send_text(
                        json.dumps({"id": msg.get("id"), "error": str(e)})
                    )

    except WebSocketDisconnect:
        logger.info("Client WS disconnected")
    except Exception:
        logger.exception("Client WS error")
    finally:
        for channel, queue in subscriptions.items():
            bridge.unsubscribe_stream(channel, queue)
        for task in tasks:
            task.cancel()
