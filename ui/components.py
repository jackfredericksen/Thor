"""
Dashboard UI components using Rich library
"""

from datetime import datetime
from typing import Dict, List, Any
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.console import Group
from .theme import Theme


class DashboardComponents:
    """Reusable UI components for the dashboard"""

    def __init__(self):
        self.theme = Theme()

    def create_header(self, stats: Dict[str, Any]) -> Panel:
        """Create header panel with bot status"""
        status = stats.get('status', 'stopped')
        cycle = stats.get('cycle_count', 0)
        discovered = stats.get('total_discovered', 0)
        filtered = stats.get('total_filtered', 0)
        trades = stats.get('total_trades', 0)
        uptime = stats.get('uptime', 0)

        # Format uptime
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        uptime_str = f"{hours}h {minutes}m"

        # Status indicator
        status_color = self.theme.get_status_color(status)
        status_emoji = '🟢' if status == 'running' else '🟡' if status == 'paused' else '🔴'

        header_text = Text()
        header_text.append("THOR MEMECOIN SNIPING BOT", style="bold cyan")
        header_text.append(" - Status: ", style="white")
        header_text.append(f"{status_emoji} {status.upper()}", style=f"bold {status_color}")
        header_text.append(" | Mode: ", style="white")
        header_text.append("🔴 LIVE TRADING", style="bold red blink")
        header_text.append(f" | Cycle: {cycle}", style="white")

        stats_text = Text()
        stats_text.append(f"Discovered: {discovered:,} | ", style="cyan")
        stats_text.append(f"Filtered: {filtered:,} | ", style="green")
        stats_text.append(f"Trades: {trades} | ", style="yellow")
        stats_text.append(f"Uptime: {uptime_str}", style="magenta")

        content = Group(header_text, stats_text)
        return Panel(content, border_style="cyan", padding=(0, 1))

    def create_token_table(self, tokens: List[Dict[str, Any]]) -> Panel:
        """Create live token feed table"""
        table = Table(title="🔥 LIVE TOKEN FEED (Top 10)", title_style="bold yellow", border_style="yellow")

        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Price", style="white", justify="right", width=12)
        table.add_column("24h Change", justify="right", width=11)
        table.add_column("Volume", justify="right", width=10)
        table.add_column("Age", style="magenta", justify="right", width=8)
        table.add_column("Score", justify="right", width=6)

        for token in tokens[:10]:
            symbol = token.get('symbol', 'N/A')
            price = token.get('price', 0)
            change_24h = token.get('price_change_24h', 0)
            volume = token.get('daily_volume_usd', 0)
            age_hours = token.get('age_hours', 0)
            score = token.get('filter_score', 0)

            # Format values
            price_str = f"${price:.6f}" if price < 0.01 else f"${price:.4f}"
            change_str = self.theme.format_percentage(change_24h)
            volume_str = self.theme.format_currency(volume)
            age_str = f"{age_hours:.0f}h" if age_hours < 24 else f"{age_hours/24:.1f}d"
            score_str = f"{score:.2f}"

            # Color based on change
            change_color = "bright_green" if change_24h > 0 else "bright_red"
            score_color = "green" if score > 0.7 else "yellow" if score > 0.5 else "white"

            table.add_row(
                symbol,
                price_str,
                Text(change_str, style=change_color),
                volume_str,
                age_str,
                Text(score_str, style=score_color)
            )

        if not tokens:
            table.add_row("No tokens yet...", "", "", "", "", "")

        return Panel(table, border_style="yellow")

    def create_portfolio_panel(self, portfolio: Dict[str, Any], positions: List[Dict[str, Any]]) -> Panel:
        """Create portfolio overview panel"""
        total_value = portfolio.get('portfolio_value', 0)
        cash = portfolio.get('cash_balance', 0)
        position_value = portfolio.get('total_exposure', 0)
        unrealized_pnl = portfolio.get('unrealized_pnl', 0)
        num_positions = portfolio.get('number_of_positions', 0)

        # Calculate percentages
        cash_pct = (cash / total_value * 100) if total_value > 0 else 0
        position_pct = (position_value / total_value * 100) if total_value > 0 else 0

        # Format values
        total_str = self.theme.format_currency(total_value)
        cash_str = self.theme.format_currency(cash)
        position_str = self.theme.format_currency(position_value)
        pnl_str = self.theme.format_currency(unrealized_pnl)
        pnl_pct = (unrealized_pnl / total_value * 100) if total_value > 0 else 0

        # Colors
        pnl_color = self.theme.get_pnl_color(unrealized_pnl)

        # Create content
        lines = []
        lines.append(Text("💰 PORTFOLIO", style="bold green"))
        lines.append(Text())
        lines.append(Text(f"Total Value:    {total_str}", style="white"))
        lines.append(Text(f"Cash:           {cash_str}  ({cash_pct:.1f}%)", style="cyan"))
        lines.append(Text(f"Positions:      {position_str}  ({position_pct:.1f}%)", style="yellow"))
        lines.append(Text(f"Unrealized P&L: {pnl_str}  ({pnl_pct:+.1f}%)", style=pnl_color))
        lines.append(Text())
        lines.append(Text(f"Active Positions: {num_positions}", style="magenta"))

        # Add position details
        if positions:
            lines.append(Text())
            for pos in positions[:5]:  # Show top 5 positions
                symbol = pos.get('symbol', 'N/A')
                quantity = pos.get('quantity', 0)
                value = pos.get('current_value', 0)
                pnl = pos.get('unrealized_pnl', 0)
                entry_price = pos.get('entry_price', 0)

                pnl_pct_pos = (pnl / value * 100) if value > 0 else 0
                pnl_color_pos = self.theme.get_pnl_color(pnl)

                pos_text = Text()
                pos_text.append(f"• {symbol} ", style="cyan")
                pos_text.append(f"{quantity:.0f} ", style="white")
                pos_text.append(f"{self.theme.format_currency(value)} ", style="yellow")
                pos_text.append(f"{pnl:+.0f} ({pnl_pct_pos:+.1f}%) ", style=pnl_color_pos)
                pos_text.append(f"[@ ${entry_price:.6f}]", style="dim")
                lines.append(pos_text)

        content = Group(*lines)
        return Panel(content, border_style="green", padding=(1, 2))

    def create_trade_log_panel(self, trades: List[Dict[str, Any]]) -> Panel:
        """Create recent trades panel"""
        table = Table(title="📝 RECENT TRADES (Last 15)", title_style="bold cyan", show_header=True, border_style="cyan")

        table.add_column("Time", style="dim", width=8)
        table.add_column("Action", width=5)
        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Amount", justify="right", width=10)
        table.add_column("Price", justify="right", width=12)
        table.add_column("Value", justify="right", width=10)
        table.add_column("Details", width=15)

        for trade in trades[-15:]:  # Last 15 trades
            timestamp = trade.get('timestamp', datetime.now())
            action = trade.get('action', 'N/A').upper()
            symbol = trade.get('symbol', 'N/A')
            quantity = trade.get('quantity', 0)
            price = trade.get('price', 0)
            confidence = trade.get('confidence', 0)
            pnl = trade.get('pnl', None)

            # Format time
            time_str = timestamp.strftime("%H:%M:%S") if isinstance(timestamp, datetime) else "N/A"

            # Format values
            amount_str = f"{quantity:.0f}" if quantity > 1 else f"{quantity:.4f}"
            price_str = f"${price:.6f}" if price < 0.01 else f"${price:.4f}"
            value_str = self.theme.format_currency(quantity * price)

            # Action color
            action_color = self.theme.get_signal_color(action.lower())

            # Details
            if pnl is not None:
                pnl_color = self.theme.get_pnl_color(pnl)
                details = Text(f"{pnl:+.0f} ({pnl/value*100:+.1f}%)", style=pnl_color)
            else:
                details = Text(f"{action} ({confidence:.2f})", style="dim")

            table.add_row(
                time_str,
                Text(action, style=action_color),
                symbol,
                amount_str,
                price_str,
                value_str,
                details
            )

        if not trades:
            table.add_row("No trades yet...", "", "", "", "", "", "")

        return Panel(table, border_style="cyan")

    def create_log_panel(self, logs: List[Dict[str, Any]]) -> Panel:
        """Create system log panel"""
        from .log_buffer import LogBuffer

        log_buffer_helper = LogBuffer(max_size=100)
        lines = []

        for log in logs[-20:]:  # Last 20 logs
            timestamp = log.get('timestamp', datetime.now())
            level = log.get('level', 'INFO')
            message = log.get('message', '')

            time_str = timestamp.strftime("%H:%M:%S") if isinstance(timestamp, datetime) else "N/A"
            color = log_buffer_helper.get_level_color(level)

            log_text = Text()
            log_text.append(f"{time_str} ", style="dim")
            log_text.append(f"{level:8s} ", style=color)
            log_text.append(message, style="white")
            lines.append(log_text)

        if not logs:
            lines.append(Text("Waiting for logs...", style="dim"))

        content = Group(*lines)
        return Panel(content, title="📋 SYSTEM LOG", title_align="left", border_style="white", padding=(0, 1))

    def create_controls_footer(self) -> Text:
        """Create keyboard controls footer"""
        footer = Text()
        footer.append("Press: ", style="dim")
        footer.append("[p]", style="bold yellow")
        footer.append("ause ", style="dim")
        footer.append("[c]", style="bold yellow")
        footer.append("ommand ", style="dim")
        footer.append("[r]", style="bold yellow")
        footer.append("efresh ", style="dim")
        footer.append("[s]", style="bold red")
        footer.append("top ", style="dim")
        footer.append("[q]", style="bold red")
        footer.append("uit", style="dim")
        return footer
