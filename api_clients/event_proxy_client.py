# api_clients/event_proxy_client.py
"""
Client for the parser-proxy-ws Rust sidecar (0xfnzero/parser-proxy-ws).

The sidecar connects to Yellowstone gRPC and publishes pool-creation
events as JSON WebSocket messages.  Thor consumes them here.

All Thor code works without this sidecar — the client goes into
"disabled" mode when EVENT_PROXY_URL is not set.
"""
import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BACKOFF_SEQUENCE = [2, 4, 8, 16, 32, 60]

# Stablecoins / wrapped SOL we don't want to trade directly
_SKIP_MINTS = {
    "So11111111111111111111111111111111111111112",  # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
}


class EventProxyClient:
    """
    Background WebSocket listener for the parser-proxy-ws sidecar.

    Event shape published by the sidecar:
    {
      "type": "pool_create",
      "signature": "...",
      "slot": 12345,
      "base_mint": "...",
      "quote_mint": "...",
      "sol_amount": 10.0,
      "dex": "raydium|pumpswap|meteora"
    }
    """

    def __init__(self, proxy_url: str = ""):
        self._url = proxy_url or os.getenv("EVENT_PROXY_URL", "")
        self._pending: deque = deque(maxlen=500)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self):
        """Start background listener.  No-op if EVENT_PROXY_URL not set."""
        if not self._url:
            logger.debug("EventProxyClient: EVENT_PROXY_URL not set — disabled")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="event-proxy-ws"
        )
        self._thread.start()
        logger.info(f"EventProxyClient started → {self._url}")

    def stop(self):
        self._running = False

    def get_pending_events(self) -> List[Dict[str, Any]]:
        """Drain and return all queued pool-creation events."""
        events = []
        while self._pending:
            try:
                events.append(self._pending.popleft())
            except IndexError:
                break
        return events

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen())
        finally:
            loop.close()

    async def _listen(self):
        backoff_idx = 0
        while self._running:
            try:
                await self._connect_and_receive()
                backoff_idx = 0
            except Exception as exc:
                if not self._running:
                    break
                delay = _BACKOFF_SEQUENCE[min(backoff_idx, len(_BACKOFF_SEQUENCE) - 1)]
                logger.warning(
                    f"EventProxy WS error: {exc}. Reconnecting in {delay}s…"
                )
                backoff_idx += 1
                await asyncio.sleep(delay)

    async def _connect_and_receive(self):
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed — event proxy client cannot start")
            self._running = False
            return

        logger.info(f"EventProxy connecting to {self._url}…")
        async with websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            logger.info("EventProxy connected")
            async for raw in ws:
                if not self._running:
                    break
                try:
                    event = json.loads(raw)
                    token = self._event_to_token(event)
                    if token:
                        self._pending.append(token)
                except Exception as exc:
                    logger.debug(f"EventProxy parse error: {exc}")

    @staticmethod
    def _event_to_token(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a pool_create event to Thor's standard token dict."""
        if event.get("type") != "pool_create":
            return None

        # Determine which mint is the non-SOL/non-stable token
        base_mint = event.get("base_mint", "")
        quote_mint = event.get("quote_mint", "")

        # Prefer base mint; fall back to quote if base is a stable
        if base_mint and base_mint not in _SKIP_MINTS:
            token_mint = base_mint
        elif quote_mint and quote_mint not in _SKIP_MINTS:
            token_mint = quote_mint
        else:
            return None

        dex = event.get("dex", "unknown")
        return {
            "address": token_mint,
            "symbol": "???",
            "name": f"New {dex} pool",
            "price_usd": 0.0,
            "market_cap": 0.0,
            "age_hours": 0.0,
            "daily_volume_usd": 0.0,
            "liquidity_usd": float(event.get("sol_amount", 0) or 0) * 150.0,
            "is_migration": False,
            "discovery_source": "event_proxy",
            "source_priority": 25,
            "memecoin_score": 3.8,
            "pumpfun": dex in ("pumpswap", "pumpfun"),
            "dex_id": dex,
            "event_proxy_slot": event.get("slot"),
            "event_proxy_tx": event.get("signature", ""),
            "discovered_at": datetime.now().isoformat(),
        }


# Module-level singleton
_client: Optional[EventProxyClient] = None


def get_event_proxy_client() -> EventProxyClient:
    global _client
    if _client is None:
        _client = EventProxyClient()
        _client.start()
    return _client
