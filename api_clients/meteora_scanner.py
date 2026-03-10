# api_clients/meteora_scanner.py
"""
Meteora DLMM + DBC (believe.app) new-pool detector.

Connects to Helius WSS using logsSubscribe for two Meteora program IDs:
  - DLMM: LBUZKhRxPF3XUpBCjp4YzTKgLe4eLDhZ83vTssEB6qMa
  - DBC (believe.app): dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN

On "Program log: Instruction: InitializeLbPair" (DLMM) or
   "Program log: Instruction: CreatePool" (DBC),
fetches pair details from DexScreener and enqueues as a token dict.

Requires HELIUS_WSS_URL.  Silently disabled if not set.
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

import requests

logger = logging.getLogger(__name__)

METEORA_DLMM_PROGRAM = "LBUZKhRxPF3XUpBCjp4YzTKgLe4eLDhZ83vTssEB6qMa"
METEORA_DBC_PROGRAM = "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN"

# Log patterns that indicate a new pool was created
_INIT_PATTERNS = (
    "Program log: Instruction: InitializeLbPair",  # DLMM
    "Program log: Instruction: CreatePool",          # DBC
    "Program log: Instruction: Initialize",          # generic fallback
)

_BACKOFF_SEQUENCE = [2, 4, 8, 16, 32, 60]


def _make_subscribe_msg(program_id: str, sub_id: int) -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": sub_id,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [program_id]},
            {"commitment": "confirmed"},
        ],
    })


class MeteoraScanner:
    """
    Background monitor that detects new Meteora liquidity pools in real-time.

    Usage:
        scanner = MeteoraScanner()
        scanner.start()
        ...
        tokens = scanner.get_pending_pools()
    """

    def __init__(self, helius_wss_url: str = ""):
        self._url = helius_wss_url or os.getenv("HELIUS_WSS_URL", "")
        self._pending: deque = deque(maxlen=200)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self):
        """Start background listener.  No-op if HELIUS_WSS_URL not set."""
        if not self._url:
            logger.warning(
                "MeteoraScanner: HELIUS_WSS_URL not set — Meteora detection disabled"
            )
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="meteora-scanner"
        )
        self._thread.start()
        logger.info("MeteoraScanner started (DLMM + DBC)")

    def stop(self):
        self._running = False

    def get_pending_pools(self) -> List[Dict[str, Any]]:
        """Drain and return all detected new Meteora pools."""
        pools = []
        while self._pending:
            try:
                pools.append(self._pending.popleft())
            except IndexError:
                break
        return pools

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                asyncio.gather(
                    self._listen(METEORA_DLMM_PROGRAM, "dlmm"),
                    self._listen(METEORA_DBC_PROGRAM, "dbc"),
                )
            )
        finally:
            loop.close()

    async def _listen(self, program_id: str, label: str):
        backoff_idx = 0
        sub_id = 1 if label == "dlmm" else 2
        while self._running:
            try:
                await self._connect(program_id, label, sub_id)
                backoff_idx = 0
            except Exception as exc:
                if not self._running:
                    break
                delay = _BACKOFF_SEQUENCE[min(backoff_idx, len(_BACKOFF_SEQUENCE) - 1)]
                logger.warning(
                    f"MeteoraScanner [{label}] error: {exc}. Reconnecting in {delay}s…"
                )
                backoff_idx += 1
                await asyncio.sleep(delay)

    async def _connect(self, program_id: str, label: str, sub_id: int):
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed — MeteoraScanner cannot start")
            self._running = False
            return

        subscribe_msg = _make_subscribe_msg(program_id, sub_id)
        logger.info(f"MeteoraScanner [{label}] connecting…")

        async with websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(subscribe_msg)
            logger.info(f"MeteoraScanner [{label}] subscribed to {program_id[:16]}…")

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                    self._handle_message(msg, label)
                except Exception as exc:
                    logger.debug(f"MeteoraScanner [{label}] parse error: {exc}")

    def _handle_message(self, msg: Dict[str, Any], label: str):
        params = msg.get("params", {})
        result = params.get("result", {})
        value = result.get("value", {})
        logs = value.get("logs", [])
        signature = value.get("signature", "")

        is_new_pool = any(
            any(log.startswith(pat) for pat in _INIT_PATTERNS)
            for log in logs
        )
        if not is_new_pool:
            return

        logger.info(
            f"🌊 Meteora [{label}] new pool detected! tx={signature[:16]}…"
        )
        token = self._fetch_pool_token(signature, label)
        if token:
            self._pending.append(token)

    def _fetch_pool_token(
        self, signature: str, label: str
    ) -> Optional[Dict[str, Any]]:
        """Resolve the new pool's token from DexScreener."""
        try:
            time.sleep(3)  # Wait for indexing
            dex_id = "meteora" if label == "dlmm" else "meteora_dbc"
            url = (
                "https://api.dexscreener.com/latest/dex/search"
                f"?q={dex_id}&sort=created&limit=5"
            )
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                return None

            pairs = resp.json().get("pairs", [])
            for pair in pairs:
                if pair.get("chainId") != "solana":
                    continue
                base = pair.get("baseToken", {})
                address = base.get("address", "")
                if not address:
                    continue
                return self._build_token(address, pair, label)

        except Exception as exc:
            logger.debug(f"MeteoraScanner DexScreener lookup failed: {exc}")

        return {
            "address": "",
            "symbol": "METEORA",
            "name": f"Meteora {label.upper()} new pool",
            "is_migration": False,
            "discovery_source": "meteora_scanner",
            "source_priority": 18,
            "age_hours": 0.0,
            "price_usd": 0.0,
            "market_cap": 0.0,
            "daily_volume_usd": 0.0,
            "liquidity_usd": 0.0,
            "memecoin_score": 3.2,
            "meteora_label": label,
            "discovered_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _build_token(address: str, pair: Dict, label: str) -> Dict[str, Any]:
        base = pair.get("baseToken", {})
        age_ms = pair.get("pairCreatedAt", 0)
        age_hours = 0.0
        if age_ms:
            age_hours = (time.time() - age_ms / 1000) / 3600

        return {
            "address": address,
            "symbol": base.get("symbol", "???"),
            "name": base.get("name", base.get("symbol", "???")),
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "market_cap": float(pair.get("fdv", 0) or 0),
            "daily_volume_usd": float((pair.get("volume") or {}).get("h24", 0)),
            "liquidity_usd": float((pair.get("liquidity") or {}).get("usd", 0)),
            "age_hours": age_hours,
            "is_migration": False,
            "discovery_source": "meteora_scanner",
            "source_priority": 18,
            "memecoin_score": 3.2,
            "meteora_label": label,
            "dex_id": pair.get("dexId", "meteora"),
            "pair_address": pair.get("pairAddress", ""),
            "discovered_at": datetime.now().isoformat(),
        }


# Module-level singleton
_scanner: Optional[MeteoraScanner] = None


def get_meteora_scanner() -> MeteoraScanner:
    global _scanner
    if _scanner is None:
        _scanner = MeteoraScanner()
        _scanner.start()
    return _scanner
