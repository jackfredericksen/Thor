"""
Main dashboard orchestrator using Rich Live display
"""

import time
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from typing import TYPE_CHECKING

from .components import DashboardComponents
from .log_buffer import LogBuffer
from .theme import theme

if TYPE_CHECKING:
    from main import TradingBot


class Dashboard:
    """Main dashboard for Thor trading bot"""

    def __init__(self, bot: 'TradingBot'):
        self.bot = bot
        self.console = Console(theme=theme)
        self.components = DashboardComponents()
        self.log_buffer = LogBuffer(max_size=1000)
        self.running = True
        self.last_update = time.time()

    def create_layout(self) -> Layout:
        """Create the dashboard layout"""
        layout = Layout()

        # Split into header, body, footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1)
        )

        # Split body into left and right
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )

        # Split left into tokens and trades
        layout["left"].split_column(
            Layout(name="tokens", ratio=2),
            Layout(name="trades", ratio=3)
        )

        # Split right into portfolio and logs
        layout["right"].split_column(
            Layout(name="portfolio", ratio=1),
            Layout(name="logs", ratio=1)
        )

        return layout

    def update_layout(self, layout: Layout):
        """Update all panels with latest data"""
        try:
            # Get data from bot
            stats = self.bot.get_dashboard_stats() if hasattr(self.bot, 'get_dashboard_stats') else self._get_default_stats()
            tokens = self.bot.get_latest_tokens() if hasattr(self.bot, 'get_latest_tokens') else []
            trades = self.bot.get_recent_trades() if hasattr(self.bot, 'get_recent_trades') else []
            logs = self.log_buffer.get_recent(20)

            # Get portfolio data
            portfolio = {}
            positions = []
            if hasattr(self.bot, 'trader') and hasattr(self.bot.trader, 'get_portfolio_summary'):
                portfolio = self.bot.trader.get_portfolio_summary()
            if hasattr(self.bot, 'trader') and hasattr(self.bot.trader, 'risk_manager'):
                positions = [
                    {
                        'symbol': pos.symbol,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'current_value': pos.quantity * pos.current_price,
                        'unrealized_pnl': pos.unrealized_pnl
                    }
                    for pos in self.bot.trader.risk_manager.positions.values()
                ]

            # Update panels
            layout["header"].update(self.components.create_header(stats))
            layout["tokens"].update(self.components.create_token_table(tokens))
            layout["portfolio"].update(self.components.create_portfolio_panel(portfolio, positions))
            layout["trades"].update(self.components.create_trade_log_panel(trades))
            layout["logs"].update(self.components.create_log_panel(logs))
            layout["footer"].update(self.components.create_controls_footer())

            self.last_update = time.time()

        except Exception as e:
            # Fallback to safe defaults
            layout["header"].update(self.components.create_header(self._get_default_stats()))
            layout["footer"].update(self.components.create_controls_footer())

    def _get_default_stats(self) -> dict:
        """Get default stats when bot data not available"""
        return {
            'status': 'initializing',
            'cycle_count': getattr(self.bot, 'cycle_count', 0),
            'total_discovered': getattr(self.bot, 'total_tokens_discovered', 0),
            'total_filtered': getattr(self.bot, 'total_tokens_filtered', 0),
            'total_trades': getattr(self.bot, 'total_trades_executed', 0),
            'uptime': time.time() - getattr(self.bot, 'start_time', time.time()),
        }

    def stop(self):
        """Stop the dashboard"""
        self.running = False
