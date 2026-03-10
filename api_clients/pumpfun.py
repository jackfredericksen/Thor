# api_clients/pumpfun.py
"""
PumpFun real-time token discovery via PumpPortal WebSocket.

PumpPortal provides a free public WebSocket at wss://pumpportal.fun/api/data
that streams new token creation events in real-time.
"""
import asyncio
import json
import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# PumpPortal WSS endpoint
PUMPPORTAL_WSS_URL = "wss://pumpportal.fun/api/data"

# Subscribe messages
_MSG_NEW_TOKEN = json.dumps({"method": "subscribeNewToken"})

# Reconnect backoff: 2, 4, 8, 16, 32, 60 seconds
_BACKOFF_SEQUENCE = [2, 4, 8, 16, 32, 60]


class PumpFunWebSocketClient:
    """
    Background WebSocket client that streams new pump.fun token launches.

    Usage:
        client = PumpFunWebSocketClient()
        client.start()
        ...
        tokens = client.get_pending_tokens()  # drain deque
    """

    def __init__(self, sol_price_getter=None):
        """
        Args:
            sol_price_getter: Optional callable() -> float that returns live SOL/USD.
                              Defaults to a simple cached fetch from Jupiter.
        """
        self._pending: deque = deque(maxlen=500)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sol_price_getter = sol_price_getter
        self._sol_price_cache: float = 150.0
        self._sol_price_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the background listener thread (idempotent)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="pumpfun-ws")
        self._thread.start()
        logger.info("PumpFunWebSocketClient started")

    def stop(self):
        """Stop the background listener."""
        self._running = False

    def get_pending_tokens(self) -> List[Dict[str, Any]]:
        """Drain and return all queued token events."""
        tokens = []
        while self._pending:
            try:
                tokens.append(self._pending.popleft())
            except IndexError:
                break
        return tokens

    # Alias used by PumpFunClient.fetch_new_tokens()
    fetch_new_tokens = get_pending_tokens

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        """Entry point for background thread — owns its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen())
        finally:
            loop.close()

    async def _listen(self):
        """Async loop: connect → subscribe → receive → reconnect."""
        backoff_idx = 0
        while self._running:
            try:
                await self._connect_and_receive()
                backoff_idx = 0  # Reset on clean disconnect
            except Exception as exc:
                if not self._running:
                    break
                delay = _BACKOFF_SEQUENCE[min(backoff_idx, len(_BACKOFF_SEQUENCE) - 1)]
                logger.warning(f"PumpFun WS error: {exc}. Reconnecting in {delay}s…")
                backoff_idx += 1
                await asyncio.sleep(delay)

    async def _connect_and_receive(self):
        """Single connection lifetime."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets>=12.0")
            self._running = False
            return

        logger.info(f"Connecting to {PUMPPORTAL_WSS_URL}…")
        async with websockets.connect(
            PUMPPORTAL_WSS_URL,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(_MSG_NEW_TOKEN)
            logger.info("PumpFun WS: subscribed to new tokens")

            async for raw in ws:
                if not self._running:
                    break
                try:
                    event = json.loads(raw)
                    token = self._event_to_token(event)
                    if token:
                        self._pending.append(token)
                except Exception as exc:
                    logger.debug(f"PumpFun WS parse error: {exc}")

    def _event_to_token(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a PumpPortal new-token event to Thor's standard token dict."""
        mint = event.get("mint", "").strip()
        if not mint:
            return None

        symbol = event.get("symbol", "").strip() or "???"
        name = event.get("name", symbol).strip()

        sol_price = self._get_sol_price()
        raw_sol_price = float(event.get("sol_price", 0) or 0)
        price_usd = raw_sol_price * sol_price if raw_sol_price else 0.0

        return {
            "address": mint,
            "symbol": symbol,
            "name": name,
            "price_usd": price_usd,
            "market_cap": float(event.get("market_cap", 0) or 0),
            "age_hours": 0.0,
            "discovery_source": "pumpfun_ws",
            "source_priority": 15,
            "metadata_uri": event.get("uri") or event.get("metadata_uri"),
            "twitter": event.get("twitter"),
            "telegram": event.get("telegram"),
            "website": event.get("website"),
            "creator": event.get("traderPublicKey") or event.get("creator"),
            "initial_buy_sol": float(event.get("solAmount", 0) or event.get("sol_amount", 0) or 0),
            "is_migration": False,
            "pumpfun": True,
            "daily_volume_usd": 0.0,
            "liquidity_usd": 0.0,
            "price_change_24h": 0.0,
            "memecoin_score": 3.5,  # Brand-new pump.fun launches get high score
        }

    def _get_sol_price(self) -> float:
        """Return cached SOL/USD price (refreshed every 60s)."""
        now = time.time()
        if now - self._sol_price_ts < 60:
            return self._sol_price_cache

        # Try caller-supplied getter first
        if self._sol_price_getter:
            try:
                self._sol_price_cache = float(self._sol_price_getter())
                self._sol_price_ts = now
                return self._sol_price_cache
            except Exception:
                pass

        # Fallback: synchronous Jupiter fetch
        try:
            import urllib.request
            SOL_MINT = "So11111111111111111111111111111111111111112"
            url = f"https://price.jup.ag/v6/price?ids={SOL_MINT}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                self._sol_price_cache = float(data["data"][SOL_MINT]["price"])
                self._sol_price_ts = now
        except Exception:
            pass  # Keep existing cached value

        return self._sol_price_cache


# ---------------------------------------------------------------------------
# Legacy wrapper kept for backward-compat (other modules imported PumpFunClient)
# ---------------------------------------------------------------------------

class PumpFunClient:
    """
    Thin wrapper around PumpFunWebSocketClient with the old interface.
    On first use, starts the WebSocket listener automatically.
    """

    def __init__(self):
        self._ws_client = PumpFunWebSocketClient()
        self._ws_client.start()

    def fetch_new_tokens(self, limit: int = 50) -> Dict[str, Any]:
        """Drain pending WebSocket events and return them in the old envelope format."""
        tokens = self._ws_client.get_pending_tokens()
        return {
            "tokens": tokens[:limit],
            "status": "success",
            "message": f"Fetched {len(tokens)} real-time pump.fun tokens",
        }

    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Stub — real-time WS doesn't support individual token lookup."""
        return {"address": token_address, "status": "not_implemented"}

    def health_check(self) -> bool:
        return self._ws_client._running
