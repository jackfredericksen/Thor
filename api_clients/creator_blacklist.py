# api_clients/creator_blacklist.py
"""
Persistent creator wallet blacklist for pump.fun rug-pull prevention.

Wallets are added:
  - Manually via add()
  - Automatically by contract_analyzer when a rug is detected

The blacklist is stored as JSON in data/creator_blacklist.json so it
survives restarts and grows over time.
"""
import json
import logging
import os
import threading
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "creator_blacklist.json"
)

# Seed list — known bad actors compiled from community reports
_SEED_BLACKLIST = {
    # Format: "wallet_address": "reason"
    # Add known ruggers here
}


class CreatorBlacklist:
    """
    Thread-safe JSON-backed blacklist of known rug-pull creator wallets.
    """

    def __init__(self, path: str = _DEFAULT_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict = {}  # {wallet: {reason, added_at, tokens}}
        self._load()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def is_blacklisted(self, wallet: str) -> Tuple[bool, str]:
        """
        Check if ``wallet`` is blacklisted.

        Returns (is_blacklisted: bool, reason: str).
        """
        if not wallet:
            return False, ""
        with self._lock:
            entry = self._data.get(wallet)
        if entry:
            return True, entry.get("reason", "Known bad actor")
        return False, ""

    def add(self, wallet: str, reason: str):
        """Manually blacklist a wallet address."""
        if not wallet:
            return
        with self._lock:
            if wallet not in self._data:
                self._data[wallet] = {
                    "reason": reason,
                    "added_at": datetime.now().isoformat(),
                    "tokens": [],
                    "auto": False,
                }
                self._save()
                logger.warning(f"Blacklisted wallet {wallet[:12]}… — {reason}")

    def auto_add_rugger(self, wallet: str, token: str, reason: str = ""):
        """
        Automatically add a creator wallet after a rug is detected.
        Called by contract_analyzer when mint/freeze authority is not renounced.
        """
        if not wallet:
            return
        reason = reason or "Auto-detected rug (mint/freeze authority active)"
        with self._lock:
            if wallet not in self._data:
                self._data[wallet] = {
                    "reason": reason,
                    "added_at": datetime.now().isoformat(),
                    "tokens": [token],
                    "auto": True,
                }
            else:
                # Append to known rugged tokens list
                self._data[wallet]["tokens"] = list(
                    set(self._data[wallet].get("tokens", []) + [token])
                )
            self._save()
        logger.warning(
            f"Auto-blacklisted creator {wallet[:12]}… token={token[:12]}… "
            f"({reason})"
        )

    def remove(self, wallet: str):
        """Remove a wallet from the blacklist."""
        with self._lock:
            if wallet in self._data:
                del self._data[wallet]
                self._save()

    def count(self) -> int:
        with self._lock:
            return len(self._data)

    def all_entries(self) -> dict:
        with self._lock:
            return dict(self._data)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            if os.path.exists(self._path):
                with open(self._path, "r") as f:
                    self._data = json.load(f)
            else:
                # Seed with known bad actors
                self._data = {}
                for wallet, reason in _SEED_BLACKLIST.items():
                    self._data[wallet] = {
                        "reason": reason,
                        "added_at": "2025-01-01T00:00:00",
                        "tokens": [],
                        "auto": False,
                    }
                self._save()
            logger.info(
                f"CreatorBlacklist loaded: {len(self._data)} entries from {self._path}"
            )
        except Exception as exc:
            logger.warning(f"CreatorBlacklist load failed: {exc} — starting empty")
            self._data = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as exc:
            logger.error(f"CreatorBlacklist save failed: {exc}")


# Module-level singleton
_blacklist: Optional[CreatorBlacklist] = None


def get_creator_blacklist() -> CreatorBlacklist:
    global _blacklist
    if _blacklist is None:
        _blacklist = CreatorBlacklist()
    return _blacklist
