import asyncio
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from hoodlink.config import settings

logger = logging.getLogger(__name__)


class Bridge:
    def __init__(self) -> None:
        self._ws: WebSocket | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._stream_handlers: dict[str, list[asyncio.Queue]] = {}

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def handle_extension(self, ws: WebSocket) -> None:
        await ws.accept()
        if self._ws is not None:
            logger.warning("Replacing existing extension connection")
            try:
                await self._ws.close(code=1000, reason="replaced")
            except Exception:
                pass
            self._cancel_pending("Extension reconnected")

        self._ws = ws
        logger.info("Extension connected")

        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                corr_id = msg.get("id")

                if corr_id and corr_id in self._pending:
                    self._pending[corr_id].set_result(msg)
                elif msg.get("channel"):
                    await self._dispatch_stream(msg)
                else:
                    logger.warning("Unhandled message: %s", msg)
        except WebSocketDisconnect:
            logger.info("Extension disconnected")
        except Exception:
            logger.exception("Bridge error")
        finally:
            self._ws = None
            self._cancel_pending("Extension disconnected")

    async def send_command(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        if not self._ws:
            raise RuntimeError("Extension not connected")

        corr_id = uuid.uuid4().hex
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[corr_id] = future

        command = {
            "id": corr_id,
            "action": "fetch",
            "url": url,
            "method": method,
            "headers": headers or {},
            "body": body,
        }
        await self._ws.send_text(json.dumps(command))

        try:
            result = await asyncio.wait_for(future, timeout=settings.bridge_timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Bridge command timed out after {settings.bridge_timeout}s")
        finally:
            self._pending.pop(corr_id, None)

        if result.get("error"):
            raise RuntimeError(f"Extension error: {result['error']}")

        return result.get("data", {})

    def subscribe_stream(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._stream_handlers.setdefault(channel, []).append(queue)
        return queue

    def unsubscribe_stream(self, channel: str, queue: asyncio.Queue) -> None:
        handlers = self._stream_handlers.get(channel, [])
        if queue in handlers:
            handlers.remove(queue)

    async def _dispatch_stream(self, msg: dict) -> None:
        channel = msg["channel"]
        for queue in self._stream_handlers.get(channel, []):
            try:
                queue.put_nowait(msg["data"])
            except asyncio.QueueFull:
                pass

    def _cancel_pending(self, reason: str) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError(reason))
        self._pending.clear()


bridge = Bridge()
