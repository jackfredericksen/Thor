# api_clients/rugcheck.py
"""
RugCheck.xyz client for Solana token security auditing.

Public API — no key required for basic reads.
Endpoint: GET https://api.rugcheck.xyz/v1/tokens/{mint}/report
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"


@dataclass
class TokenSafetyAudit:
    """Structured result from RugCheck."""
    token_address: str
    status: str  # "success" | "error" | "disabled"
    score: int = 0  # 0–100 (higher = safer)
    is_rugged: bool = False
    mint_authority: Optional[str] = None
    freeze_authority: Optional[str] = None
    top_holders: List[Dict] = field(default_factory=list)
    top_holders_pct: float = 0.0  # combined top-10 %
    risks: List[Dict] = field(default_factory=list)
    risk_names: List[str] = field(default_factory=list)
    has_danger: bool = False
    liquidity_usd: float = 0.0
    name: str = ""
    symbol: str = ""
    mutable_metadata: bool = True
    message: str = ""


class RugcheckClient:
    """
    Calls RugCheck.xyz public API to audit Solana SPL tokens.

    Works without an API key.  Pass ``api_key`` to increase rate limits.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Thor-TradingBot/1.0",
        })
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def audit_token(self, token_address: str) -> TokenSafetyAudit:
        """
        Fetch and parse a RugCheck report for ``token_address``.

        Returns a TokenSafetyAudit regardless of errors (status field
        indicates whether the call succeeded).
        """
        if not self._valid_solana_address(token_address):
            return TokenSafetyAudit(
                token_address=token_address,
                status="error",
                message="Invalid Solana token address",
            )

        url = f"{RUGCHECK_BASE}/tokens/{token_address}/report"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            return self._parse(token_address, resp.json())
        except requests.HTTPError as exc:
            logger.warning(f"RugCheck HTTP {exc.response.status_code} for {token_address[:8]}")
            return TokenSafetyAudit(
                token_address=token_address,
                status="error",
                message=f"HTTP {exc.response.status_code}",
            )
        except Exception as exc:
            logger.warning(f"RugCheck error for {token_address[:8]}: {exc}")
            return TokenSafetyAudit(
                token_address=token_address,
                status="error",
                message=str(exc),
            )

    def get_token_score(self, token_address: str) -> float:
        """Convenience: return just the 0–100 safety score."""
        return float(self.audit_token(token_address).score)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_solana_address(address: str) -> bool:
        """Quick check: Solana base58 address is 32–44 chars."""
        import re
        if not address or not isinstance(address, str):
            return False
        return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", address.strip()))

    @staticmethod
    def _parse(token_address: str, data: Dict[str, Any]) -> TokenSafetyAudit:
        """
        Map RugCheck.xyz /v1/tokens/{mint}/report response to TokenSafetyAudit.

        Response shape:
        {
          "mint": "...",
          "score": 85,
          "rugged": false,
          "risks": [{"name": "...", "description": "...",
                     "level": "danger|warning|info", "score": 30}],
          "topHolders": [{"address": "...", "pct": 12.5, "uiAmount": ...}],
          "mintAuthority": null,
          "freezeAuthority": null,
          "tokenMeta": {"name": "...", "symbol": "...", "mutable": false},
          "totalMarketLiquidity": 45000.0
        }
        """
        risks = data.get("risks") or []
        top_holders = data.get("topHolders") or []
        token_meta = data.get("tokenMeta") or {}

        top_holders_pct = sum(
            float(h.get("pct", 0)) for h in top_holders[:10]
        )
        has_danger = any(r.get("level") == "danger" for r in risks)
        risk_names = [r.get("name", "") for r in risks if r.get("name")]

        return TokenSafetyAudit(
            token_address=token_address,
            status="success",
            score=int(data.get("score", 0)),
            is_rugged=bool(data.get("rugged", False)),
            mint_authority=data.get("mintAuthority"),
            freeze_authority=data.get("freezeAuthority"),
            top_holders=top_holders,
            top_holders_pct=top_holders_pct,
            risks=risks,
            risk_names=risk_names,
            has_danger=has_danger,
            liquidity_usd=float(data.get("totalMarketLiquidity", 0) or 0),
            name=token_meta.get("name", ""),
            symbol=token_meta.get("symbol", ""),
            mutable_metadata=bool(token_meta.get("mutable", True)),
        )

    def health_check(self) -> bool:
        try:
            resp = self._session.get(f"{RUGCHECK_BASE}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def __del__(self):
        try:
            self._session.close()
        except Exception:
            pass
