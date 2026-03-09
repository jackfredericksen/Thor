# dex_mcp_server.py
# MCP (Model Context Protocol) server exposing Thor's DexScreener scanner to AI agents.
#
# Start standalone:
#   THOR_MCP_ENABLED=true python dex_mcp_server.py
#
# Or it can be launched automatically by main.py when THOR_MCP_ENABLED=true.
#
# Claude Desktop / Claude Code config example:
# {
#   "mcpServers": {
#     "thor": {
#       "command": "python",
#       "args": ["/path/to/Thor/dex_mcp_server.py"]
#     }
#   }
# }

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


def _safe_json(obj: Any) -> Any:
    """Recursively make an object JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(i) for i in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)


async def _do_scan(
    chains: list[str] | None = None,
    limit: int = 20,
    min_liquidity: float = 20_000,
    min_volume: float = 40_000,
    min_txns_h1: int = 15,
) -> list[dict[str, Any]]:
    from api_clients.dex_client import DexScreenerClientAsync
    from api_clients.dex_scanner import HotScanner, ScanFilters

    filters = ScanFilters(
        chains=tuple(chains or ["solana"]),
        limit=limit,
        min_liquidity_usd=min_liquidity,
        min_volume_h24_usd=min_volume,
        min_txns_h1=min_txns_h1,
    )
    async with DexScreenerClientAsync() as client:
        scanner = HotScanner(client)
        candidates = await scanner.scan(filters)

    results = []
    for c in candidates:
        p = c.pair
        a = c.analytics
        results.append({
            "symbol": p.base_symbol,
            "name": p.base_name,
            "address": p.base_address,
            "chain": p.chain_id,
            "dex": p.dex_id,
            "score": c.score,
            "tags": c.tags,
            "discovery": c.discovery,
            "price_usd": p.price_usd,
            "volume_h24": p.volume_h24,
            "volume_h1": p.volume_h1,
            "liquidity_usd": p.liquidity_usd,
            "market_cap": p.market_cap,
            "fdv": p.fdv,
            "txns_h1": p.txns_h1,
            "buys_h1": p.buys_h1,
            "sells_h1": p.sells_h1,
            "price_change_h1": p.price_change_h1,
            "price_change_h24": p.price_change_h24,
            "age_hours": p.age_hours,
            "pair_url": p.pair_url,
            "has_profile": c.has_profile,
            "boost_total": c.boost_total,
            "analytics": {
                "compression_score": a.compression_score,
                "breakout_readiness": a.breakout_readiness,
                "volume_velocity": a.volume_velocity,
                "txn_velocity": a.txn_velocity,
                "relative_strength": a.relative_strength,
                "boost_velocity": a.boost_velocity,
                "momentum_decay_ratio": a.momentum_decay_ratio,
                "fast_decay": a.fast_decay,
                "risk_score": a.risk_score,
                "risk_flags": a.risk_flags,
                "score_components": a.score_components,
            },
        })
    return results


async def _do_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    from api_clients.dex_client import DexScreenerClientAsync
    from api_clients.dex_models import PairSnapshot

    async with DexScreenerClientAsync() as client:
        rows = await client.search_pairs(query)

    results = []
    for row in rows[:limit]:
        p = PairSnapshot.from_api(row)
        results.append({
            "symbol": p.base_symbol,
            "name": p.base_name,
            "address": p.base_address,
            "chain": p.chain_id,
            "dex": p.dex_id,
            "price_usd": p.price_usd,
            "volume_h24": p.volume_h24,
            "liquidity_usd": p.liquidity_usd,
            "market_cap": p.market_cap,
            "txns_h1": p.txns_h1,
            "price_change_h1": p.price_change_h1,
            "price_change_h24": p.price_change_h24,
            "age_hours": p.age_hours,
            "pair_url": p.pair_url,
        })
    return results


async def _do_inspect(chain_id: str, token_address: str) -> list[dict[str, Any]]:
    from api_clients.dex_client import DexScreenerClientAsync
    from api_clients.dex_models import PairSnapshot
    from api_clients.dex_scoring import build_distribution_heuristics, score_hotness
    from api_clients.dex_models import HotTokenCandidate, CandidateAnalytics

    async with DexScreenerClientAsync() as client:
        rows = await client.get_token_pairs(chain_id, token_address)

    snapshots = [PairSnapshot.from_api(row) for row in rows]
    snapshots.sort(
        key=lambda p: (p.liquidity_usd, p.volume_h24, p.txns_h1), reverse=True
    )

    results = []
    for p in snapshots[:5]:
        score, tags = score_hotness(p)
        dummy = HotTokenCandidate(
            pair=p, score=score, boost_total=0, boost_count=0,
            has_profile=False, discovery="inspect", tags=tags,
            analytics=CandidateAnalytics(),
        )
        dist = build_distribution_heuristics(dummy)
        results.append({
            "symbol": p.base_symbol,
            "name": p.base_name,
            "address": p.base_address,
            "chain": p.chain_id,
            "dex": p.dex_id,
            "pair_address": p.pair_address,
            "price_usd": p.price_usd,
            "volume_h24": p.volume_h24,
            "volume_h1": p.volume_h1,
            "liquidity_usd": p.liquidity_usd,
            "market_cap": p.market_cap,
            "fdv": p.fdv,
            "txns_h1": p.txns_h1,
            "price_change_h1": p.price_change_h1,
            "price_change_h24": p.price_change_h24,
            "age_hours": p.age_hours,
            "hotness_score": score,
            "tags": tags,
            "distribution": dist,
            "pair_url": p.pair_url,
        })
    return results


async def _get_rate_stats() -> dict[str, Any]:
    """Return a summary of API rate budget usage."""
    from api_clients.dex_client import DexScreenerClientAsync
    async with DexScreenerClientAsync() as client:
        return await client.get_runtime_stats()


def _run_tool(coro) -> Any:
    """
    Run an async coroutine from a sync MCP tool handler.

    FastMCP calls tool functions synchronously, so we dispatch to a dedicated
    background thread with its own event loop. This avoids conflicts with any
    event loop the MCP framework may be running internally.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=120)


# ---------------------------------------------------------------------------
# MCP Server implementation using the `mcp` package
# ---------------------------------------------------------------------------

def build_mcp_server():
    """Build and return the FastMCP server instance."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error(
            "mcp package not installed. Run: pip install mcp"
        )
        sys.exit(1)

    mcp = FastMCP("Thor DexScreener Scanner")

    @mcp.tool()
    def scan_hot_tokens(
        chains: str = "solana",
        limit: int = 20,
        min_liquidity: float = 20_000,
        min_volume: float = 40_000,
        min_txns_h1: int = 15,
    ) -> str:
        """
        Scan for the hottest trending tokens on DexScreener.

        Uses composite scoring: volume velocity, transaction velocity,
        liquidity depth, buy pressure, boost signals, recency, and
        momentum analytics (compression, breakout readiness, relative strength).

        Args:
            chains: Comma-separated chain IDs (e.g. "solana", "solana,base")
            limit: Maximum number of tokens to return (default 20)
            min_liquidity: Minimum liquidity in USD (default $20,000)
            min_volume: Minimum 24h volume in USD (default $40,000)
            min_txns_h1: Minimum transactions in last hour (default 15)

        Returns:
            JSON array of token candidates sorted by hotness score (0-100).
        """
        chain_list = [c.strip() for c in chains.split(",") if c.strip()]
        results = _run_tool(_do_scan(
            chains=chain_list,
            limit=limit,
            min_liquidity=min_liquidity,
            min_volume=min_volume,
            min_txns_h1=min_txns_h1,
        ))
        return json.dumps(_safe_json(results), indent=2)

    @mcp.tool()
    def search_pairs(query: str, limit: int = 20) -> str:
        """
        Search for trading pairs by token name, symbol, or contract address.

        Args:
            query: Search term (name, symbol, or contract address)
            limit: Maximum number of results (default 20)

        Returns:
            JSON array of matching pairs with price, volume, and liquidity data.
        """
        results = _run_tool(_do_search(query, limit))
        return json.dumps(_safe_json(results), indent=2)

    @mcp.tool()
    def inspect_token(chain_id: str, token_address: str) -> str:
        """
        Deep analysis of a specific token across all its trading pairs.

        Returns the top 5 pairs by liquidity/volume with hotness scores,
        distribution heuristics (liquidity/mcap ratio, volume/liquidity),
        and buy/sell pressure metrics.

        Args:
            chain_id: Chain identifier (e.g. "solana", "base", "ethereum")
            token_address: Token contract address

        Returns:
            JSON array of pair analysis objects.
        """
        results = _run_tool(_do_inspect(chain_id, token_address))
        return json.dumps(_safe_json(results), indent=2)

    @mcp.tool()
    def get_rate_budget_stats() -> str:
        """
        Get DexScreener API rate limit usage statistics.

        Returns:
            JSON object with requests_total, cache_hits, throttled_429,
            retries, errors, and per-bucket wait times.
        """
        stats = _run_tool(_get_rate_stats())
        return json.dumps(_safe_json(stats), indent=2)

    return mcp


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Thor DexScreener MCP Server...")
    mcp = build_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()
