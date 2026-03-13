"""Manages the Robinhood dxFeed stream via the browser extension.

The actual WebSocket to Robinhood is opened by inject.js (browser context).
This module handles subscription state and fans events to API subscribers.

Server -> inject.js (via bridge):
  rh_connect(stream_token)   — open WS + wait for AUTH_STATE:AUTHORIZED
  rh_subscribe(subscriptions) — add subscriptions
  rh_unsubscribe(subscriptions) — remove subscriptions
  rh_disconnect              — close WS
  rh_get_subs                — return current active subscriptions

inject.js -> server (via bridge channel "rh_event"):
  {eventType, eventSymbol, ...fields} — dxFeed FEED_DATA events

inject.js -> server (via bridge channel "rh_status"):
  {connected: bool, error: str|null} — connection state changes
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class RobinhoodStream:
    def __init__(self) -> None:
        self._running: bool = False
        self._subscribers: list[asyncio.Queue] = []
        self._event_task: asyncio.Task | None = None
        self._event_queue: asyncio.Queue | None = None
        self._status_task: asyncio.Task | None = None
        self._status_queue: asyncio.Queue | None = None
        # Server-side subscription tracking: "symbol|type" -> sub dict
        self._subs: dict[str, dict] = {}

    @property
    def running(self) -> bool:
        return self._running and self._event_task is not None and not self._event_task.done()

    @property
    def subscriptions(self) -> list[dict]:
        return list(self._subs.values())

    async def start(self, stream_token: str) -> None:
        if self.running:
            return
        from hoodlink.bridge import bridge as _bridge
        # Blocks until inject.js reports AUTH_STATE:AUTHORIZED (up to 30s)
        await _bridge.rh_connect(stream_token)
        self._running = True
        self._event_queue = _bridge.subscribe_stream("rh_event")
        self._event_task = asyncio.create_task(self._forward_events())
        self._status_queue = _bridge.subscribe_stream("rh_status")
        self._status_task = asyncio.create_task(self._watch_status())
        logger.info("Robinhood stream started")

    async def stop(self) -> None:
        self._running = False
        self._subs.clear()
        for task, attr in [(self._event_task, "_event_task"), (self._status_task, "_status_task")]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._event_task = None
        self._status_task = None
        from hoodlink.bridge import bridge as _bridge
        if self._event_queue is not None:
            _bridge.unsubscribe_stream("rh_event", self._event_queue)
            self._event_queue = None
        if self._status_queue is not None:
            _bridge.unsubscribe_stream("rh_status", self._status_queue)
            self._status_queue = None
        try:
            await _bridge.rh_disconnect()
        except Exception:
            pass
        logger.info("Robinhood stream stopped")

    def reset(self) -> None:
        """Reset running state without sending rh_disconnect (e.g. on extension disconnect)."""
        self._running = False
        self._subs.clear()

    def add_subscriber(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.append(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def subscribe(self, symbol: str, event_type: str, **extra) -> None:
        from hoodlink.bridge import bridge as _bridge
        sub: dict = {"symbol": symbol, "type": event_type}
        sub.update(extra)
        await _bridge.rh_subscribe([sub])
        self._subs[f"{symbol}|{event_type}"] = sub

    async def unsubscribe(self, symbol: str, event_type: str) -> None:
        from hoodlink.bridge import bridge as _bridge
        await _bridge.rh_unsubscribe([{"symbol": symbol, "type": event_type}])
        self._subs.pop(f"{symbol}|{event_type}", None)

    async def _forward_events(self) -> None:
        assert self._event_queue is not None
        try:
            while True:
                event = await self._event_queue.get()
                self._fan_out(event)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Stream forward error")

    async def _watch_status(self) -> None:
        assert self._status_queue is not None
        try:
            while True:
                status = await self._status_queue.get()
                connected = status.get("connected", False)
                error = status.get("error")
                if not connected:
                    logger.info("Robinhood stream disconnected: %s", error)
                    self._running = False
                    self._subs.clear()
                self._fan_out({"type": "rh_status", "connected": connected, "error": error})
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Status watch error")

    def _fan_out(self, event: dict) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


stream = RobinhoodStream()
