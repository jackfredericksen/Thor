# api_clients/migration_monitor.py
"""
Pump.fun bonding-curve graduation detector.

Connects to Helius WSS using logsSubscribe and watches for
"Program log: Instruction: Migrate" emitted by the pump.fun program.

Each migration (graduation to PumpSwap) is a high-signal buy event:
the token has proved enough demand to fill its bonding curve.

Requires HELIUS_WSS_URL env var.  Silently disabled if not set.
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

PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
_BACKOFF_SEQUENCE = [2, 4, 8, 16, 32, 60]

_SUBSCRIBE_MSG = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "logsSubscribe",
    "params": [
        {"mentions": [PUMPFUN_PROGRAM_ID]},
        {"commitment": "confirmed"},
    ],
})


class MigrationMonitor:
    """
    Background WebSocket listener for pump.fun bonding-curve migrations.

    Usage:
        monitor = MigrationMonitor()
        monitor.start()       # no-op if HELIUS_WSS_URL not set
        ...
        tokens = monitor.get_pending_migrations()
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
        """Start background listener (idempotent, no-op if URL not configured)."""
        if not self._url:
            logger.warning(
                "MigrationMonitor: HELIUS_WSS_URL not set — migration detection disabled"
            )
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="migration-monitor"
        )
        self._thread.start()
        logger.info("MigrationMonitor started")

    def stop(self):
        self._running = False

    def get_pending_migrations(self) -> List[Dict[str, Any]]:
        """Drain and return all queued migration events."""
        tokens = []
        while self._pending:
            try:
                tokens.append(self._pending.popleft())
            except IndexError:
                break
        return tokens

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
                    f"MigrationMonitor WS error: {exc}. Reconnecting in {delay}s…"
                )
                backoff_idx += 1
                await asyncio.sleep(delay)

    async def _connect_and_receive(self):
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed — migration monitor cannot start")
            self._running = False
            return

        logger.info(f"MigrationMonitor connecting to {self._url[:40]}…")
        async with websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(_SUBSCRIBE_MSG)
            logger.info("MigrationMonitor: subscribed to pump.fun program logs")

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                    self._handle_message(msg)
                except Exception as exc:
                    logger.debug(f"MigrationMonitor parse error: {exc}")

    def _handle_message(self, msg: Dict[str, Any]):
        """Check if the log message signals a pump.fun migration."""
        # Helius logsSubscribe notification format:
        # {"jsonrpc":"2.0","method":"logsNotification","params":
        #   {"result":{"value":{"logs":[...],"signature":"..."}}}}
        params = msg.get("params", {})
        result = params.get("result", {})
        value = result.get("value", {})

        logs = value.get("logs", [])
        signature = value.get("signature", "")

        is_migration = any(
            "Program log: Instruction: Migrate" in log for log in logs
        )
        if not is_migration:
            return

        logger.info(f"🎓 Migration detected! tx={signature[:16]}… Fetching details…")
        token = self._fetch_migrated_token(signature)
        if token and token.get("address"):
            # Step 3C enhancements: creator history + top holders
            self._enrich_migration(token)
        if token:
            self._pending.append(token)

    def _fetch_migrated_token(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Try to resolve the token address from the migration transaction.

        Strategy: query DexScreener for the token that just appeared on PumpSwap.
        Falls back to a minimal dict with just the signature so callers can decide.
        """
        try:
            # Give DexScreener a moment to index the new pair
            time.sleep(2)
            url = (
                "https://api.dexscreener.com/latest/dex/search"
                "?q=pumpswap&sort=created&limit=5"
            )
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                pairs = resp.json().get("pairs", [])
                for pair in pairs:
                    if pair.get("chainId") != "solana":
                        continue
                    base = pair.get("baseToken", {})
                    address = base.get("address", "")
                    if not address:
                        continue
                    return self._build_migration_token(address, pair)
        except Exception as exc:
            logger.debug(f"MigrationMonitor DexScreener lookup failed: {exc}")

        # Minimal fallback: we know a migration happened but not which token
        return {
            "address": "",
            "symbol": "MIGRATED",
            "name": "Pump.fun Migration",
            "is_migration": True,
            "migration_signal": "high",
            "migration_tx": signature,
            "discovery_source": "migration_monitor",
            "source_priority": 20,
            "age_hours": 0.0,
            "price_usd": 0.0,
            "market_cap": 0.0,
            "daily_volume_usd": 0.0,
            "liquidity_usd": 0.0,
            "memecoin_score": 4.0,
            "discovered_at": datetime.now().isoformat(),
        }

    def _enrich_migration(self, token: Dict[str, Any]):
        """
        Step 3C: Enrich a migration token with creator history and top holders.

        Adds fields:
          creator_total_tokens    — how many tokens this creator has launched
          creator_best_pct        — best performer % gain by this creator
          creator_score           — creator_best_pct / max(creator_total_tokens, 1)
          top_holder_30k_count    — number of wallets holding >$30k
        """
        address = token.get("address", "")
        if not address:
            return

        # --- Top holders with >$30k ---
        try:
            top_holder_count = self._count_top_holders(address)
            token["top_holder_30k_count"] = top_holder_count
        except Exception as exc:
            logger.debug(f"Top-holder enrichment failed: {exc}")
            token["top_holder_30k_count"] = 0

        # --- Creator history via DexScreener ---
        creator = token.get("creator", "")
        if not creator:
            token.update({
                "creator_total_tokens": 0,
                "creator_best_pct": 0.0,
                "creator_score": 0.0,
            })
            return

        try:
            total, best_pct = self._fetch_creator_history(creator)
            # Reward prolific creators: bonus up to 2x for 10+ tokens launched
            volume_bonus = min(total / 10.0, 2.0)
            score = round(best_pct * (1.0 + volume_bonus * 0.2), 1)
            token.update({
                "creator_total_tokens": total,
                "creator_best_pct": best_pct,
                "creator_score": score,
            })
            logger.info(
                f"Creator {creator[:12]}…: {total} tokens, "
                f"best={best_pct:.0f}%, score={score:.1f}"
            )
        except Exception as exc:
            logger.debug(f"Creator history enrichment failed: {exc}")
            token.update({
                "creator_total_tokens": 0,
                "creator_best_pct": 0.0,
                "creator_score": 0.0,
            })

    def _count_top_holders(self, token_address: str) -> int:
        """Count wallets holding >$30k via Helius getTokenLargestAccounts."""
        sol_price = 150.0  # fallback; real price fetched separately
        threshold_tokens = 30_000 / sol_price  # approx token units at $30k

        # Use public Solana RPC — no auth needed
        try:
            resp = requests.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenLargestAccounts",
                    "params": [token_address],
                },
                timeout=8,
            )
            accounts = resp.json().get("result", {}).get("value", [])
            # uiAmount is in token units; we use $30k / token_price as threshold
            # Since we lack the price here we check relative dominance:
            # count wallets whose uiAmount > threshold_tokens (very rough)
            count = sum(
                1 for a in accounts
                if float(a.get("uiAmount") or 0) > threshold_tokens
            )
            return count
        except Exception:
            return 0

    @staticmethod
    def _fetch_creator_history(creator: str):
        """
        Query DexScreener for tokens created by ``creator``.
        Returns (total_count, best_performer_pct).
        """
        try:
            url = (
                "https://api.dexscreener.com/latest/dex/search"
                f"?q={creator}&sort=created&limit=50"
            )
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                return 0, 0.0

            pairs = [
                p for p in resp.json().get("pairs", [])
                if p.get("chainId") == "solana"
            ]
            if not pairs:
                return 0, 0.0

            best_pct = 0.0
            for pair in pairs:
                pct = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
                if pct > best_pct:
                    best_pct = pct

            return len(pairs), best_pct

        except Exception:
            return 0, 0.0

    @staticmethod
    def _build_migration_token(address: str, pair: Dict) -> Dict[str, Any]:
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
            "is_migration": True,
            "migration_signal": "high",
            "discovery_source": "migration_monitor",
            "source_priority": 20,
            "memecoin_score": 4.0,
            "pumpfun": True,
            "dex_id": pair.get("dexId", "pumpswap"),
            "pair_address": pair.get("pairAddress", ""),
            "discovered_at": datetime.now().isoformat(),
        }


# Module-level singleton — started lazily when first needed
_monitor: Optional[MigrationMonitor] = None


def get_migration_monitor() -> MigrationMonitor:
    global _monitor
    if _monitor is None:
        _monitor = MigrationMonitor()
        _monitor.start()
    return _monitor
