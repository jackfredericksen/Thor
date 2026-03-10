# api_clients/telegram_notifier.py
"""
Telegram notification sender for Thor.

Sends buy/sell alerts, rug-pull warnings, and P&L milestones to a
configured Telegram bot chat.

Requires:
  TELEGRAM_BOT_TOKEN — bot token from @BotFather
  TELEGRAM_CHAT_ID   — chat or channel ID to send messages to

Silently disabled if either env var is missing.
"""
import logging
import os
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

# Cumulative P&L milestones (USD) — notify once each per session
_PNL_MILESTONES = [100, 250, 500, 1_000, 2_500, 5_000, 10_000]


class TelegramNotifier:
    """Send formatted trade alerts to a Telegram chat."""

    def __init__(self):
        self._token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self._enabled = bool(self._token and self._chat_id)
        self._session_pnl = 0.0
        self._milestones_hit: set = set()

        if self._enabled:
            logger.info("TelegramNotifier: enabled")
        else:
            logger.debug("TelegramNotifier: disabled (TELEGRAM_BOT_TOKEN/CHAT_ID not set)")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def notify_buy(
        self,
        symbol: str,
        address: str,
        price_usd: float,
        cost_usd: float,
        source: str,
    ):
        short = address[:8] + "…"
        text = (
            f"🟢 <b>BUY</b> — <b>{symbol}</b>\n"
            f"💵 Price: <code>${price_usd:.6f}</code>\n"
            f"💸 Spent: <code>${cost_usd:.2f}</code>\n"
            f"📡 Source: <code>{source}</code>\n"
            f"🔑 <code>{short}</code>\n"
            f"🕐 {_now()}"
        )
        self._send(text)

    def notify_sell(
        self,
        symbol: str,
        pnl_usd: float,
        pnl_pct: float,
        reason: str,
    ):
        emoji = "🟩" if pnl_usd >= 0 else "🔴"
        sign = "+" if pnl_usd >= 0 else ""
        text = (
            f"{emoji} <b>SELL</b> — <b>{symbol}</b>\n"
            f"💰 P&L: <code>{sign}${pnl_usd:.2f} ({sign}{pnl_pct:.1f}%)</code>\n"
            f"📋 Reason: <code>{reason}</code>\n"
            f"🕐 {_now()}"
        )
        self._send(text)
        self._session_pnl += pnl_usd
        self._check_milestones()

    def notify_rug_blocked(self, symbol: str, reason: str):
        text = (
            f"🛡️ <b>RUG BLOCKED</b> — <b>{symbol}</b>\n"
            f"⚠️ {reason}\n"
            f"🕐 {_now()}"
        )
        self._send(text)

    def notify_pnl_milestone(self, milestone_usd: float):
        text = (
            f"🏆 <b>P&L MILESTONE</b>\n"
            f"Session profit hit <code>${milestone_usd:,.0f}</code>!\n"
            f"Total session P&L: <code>${self._session_pnl:,.2f}</code>\n"
            f"🕐 {_now()}"
        )
        self._send(text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_milestones(self):
        for m in _PNL_MILESTONES:
            if self._session_pnl >= m and m not in self._milestones_hit:
                self._milestones_hit.add(m)
                self.notify_pnl_milestone(m)

    def _send(self, text: str):
        if not self._enabled:
            return
        try:
            url = _API_BASE.format(token=self._token)
            resp = requests.post(
                url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=5,
            )
            if not resp.ok:
                logger.warning(
                    f"Telegram send failed: {resp.status_code} {resp.text[:80]}"
                )
        except Exception as exc:
            logger.debug(f"Telegram error: {exc}")


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")
