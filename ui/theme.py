"""
Theme and styling for Thor terminal UI
"""

from rich.style import Style
from rich.theme import Theme as RichTheme

# Color palette
COLORS = {
    'primary': '#00D9FF',      # Cyan
    'success': '#00FF41',      # Green
    'warning': '#FFB627',      # Yellow
    'danger': '#FF0055',       # Red
    'info': '#A78BFA',         # Purple
    'muted': '#6B7280',        # Gray
    'background': '#0F172A',   # Dark blue
    'foreground': '#F1F5F9',   # Light gray
}

# Status colors
STATUS_COLORS = {
    'running': 'green',
    'paused': 'yellow',
    'stopped': 'red',
    'error': 'bright_red',
}

# Signal colors
SIGNAL_COLORS = {
    'bullish': 'bright_green',
    'bearish': 'bright_red',
    'neutral': 'yellow',
}

# Create Rich theme
theme = RichTheme({
    'info': Style(color=COLORS['info']),
    'success': Style(color=COLORS['success'], bold=True),
    'warning': Style(color=COLORS['warning'], bold=True),
    'danger': Style(color=COLORS['danger'], bold=True),
    'primary': Style(color=COLORS['primary'], bold=True),
    'muted': Style(color=COLORS['muted']),
    'header': Style(color=COLORS['primary'], bold=True, underline=True),
    'live': Style(color=COLORS['danger'], bold=True, blink=True),
})

class Theme:
    """Theme manager for terminal UI"""

    @staticmethod
    def get_status_color(status: str) -> str:
        """Get color for status"""
        return STATUS_COLORS.get(status.lower(), 'white')

    @staticmethod
    def get_signal_color(signal: str) -> str:
        """Get color for trading signal"""
        return SIGNAL_COLORS.get(signal.lower(), 'white')

    @staticmethod
    def get_pnl_color(pnl: float) -> str:
        """Get color for P&L based on value"""
        if pnl > 0:
            return 'bright_green'
        elif pnl < 0:
            return 'bright_red'
        return 'yellow'

    @staticmethod
    def format_currency(value: float) -> str:
        """Format currency with appropriate color"""
        if value >= 1_000_000:
            return f"${value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value/1_000:.1f}K"
        else:
            return f"${value:.2f}"

    @staticmethod
    def format_percentage(value: float) -> str:
        """Format percentage with sign"""
        sign = '+' if value >= 0 else ''
        return f"{sign}{value:.2f}%"
