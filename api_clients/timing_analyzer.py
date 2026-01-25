# timing_analyzer.py - Launch Timing & Optimal Entry Analysis
"""
Analyzes optimal timing for memecoin entries:
- Time since pool/token launch
- Time of day (US trading hours vs Asia hours)
- Day of week patterns
- Launch momentum windows (golden window = 2-10min after Raydium listing)
"""

import logging
from typing import Dict, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class TimingAnalyzer:
    """Analyze launch timing and optimal entry windows"""

    # Trading hour patterns (UTC)
    US_TRADING_START = 14  # 9am EST / 2pm UTC
    US_TRADING_END = 22    # 5pm EST / 10pm UTC
    ASIA_TRADING_START = 0  # Midnight UTC
    ASIA_TRADING_END = 6    # 6am UTC

    # Launch timing windows (minutes)
    SNIPER_WINDOW = 2      # 0-2 min: Snipers only
    GOLDEN_WINDOW_START = 2  # 2 min: Golden window starts
    GOLDEN_WINDOW_END = 10   # 10 min: Golden window ends
    MOMENTUM_WINDOW_END = 30  # 30 min: Initial momentum expires

    def __init__(self):
        pass

    def analyze_timing(self, token_data: Dict) -> Dict:
        """
        Comprehensive timing analysis

        Returns dict with:
        - timing_score: float (0-1, higher = better timing)
        - timing_rating: str ("EXCELLENT", "GOOD", "FAIR", "POOR")
        - in_golden_window: bool
        - pool_age_minutes: float
        - time_of_day_score: float (0-1)
        - day_of_week_score: float (0-1)
        - reasons: List[str]
        - warnings: List[str]
        """
        try:
            reasons = []
            warnings = []

            # Calculate pool age
            pool_age_minutes = self._get_pool_age_minutes(token_data)

            # Check launch window
            launch_score, launch_reason, in_golden = self._analyze_launch_window(pool_age_minutes)
            reasons.append(launch_reason)

            # Check time of day
            time_score, time_reason = self._analyze_time_of_day()
            reasons.append(time_reason)

            # Check day of week
            day_score, day_reason = self._analyze_day_of_week()
            if day_reason:
                reasons.append(day_reason)

            # Calculate overall timing score
            timing_score = (
                launch_score * 0.60 +  # Launch window is most important (60%)
                time_score * 0.30 +    # Time of day (30%)
                day_score * 0.10       # Day of week (10%)
            )

            # Determine rating
            if timing_score >= 0.80:
                timing_rating = "EXCELLENT"
            elif timing_score >= 0.60:
                timing_rating = "GOOD"
            elif timing_score >= 0.40:
                timing_rating = "FAIR"
            else:
                timing_rating = "POOR"

            # Add warnings for bad timing
            if pool_age_minutes < self.SNIPER_WINDOW:
                warnings.append("⚠️ Very early - let snipers settle first")
            if pool_age_minutes > self.MOMENTUM_WINDOW_END:
                warnings.append("⚠️ Launch momentum likely expired")
            if time_score < 0.3:
                warnings.append("⚠️ Low volume trading hours")

            return {
                'timing_score': timing_score,
                'timing_rating': timing_rating,
                'in_golden_window': in_golden,
                'pool_age_minutes': pool_age_minutes,
                'time_of_day_score': time_score,
                'day_of_week_score': day_score,
                'reasons': reasons,
                'warnings': warnings
            }

        except Exception as e:
            logger.error(f"Error analyzing timing: {e}")
            return self._empty_timing()

    def _get_pool_age_minutes(self, token_data: Dict) -> float:
        """Calculate pool/token age in minutes"""
        try:
            # Try multiple timestamp fields
            timestamp = None

            # Check for pair creation time (most accurate for Raydium)
            if 'pairCreatedAt' in token_data:
                timestamp = token_data['pairCreatedAt']
            elif 'created_at' in token_data:
                timestamp = token_data['created_at']
            elif 'discovered_at' in token_data:
                timestamp = token_data['discovered_at']
            elif 'age_hours' in token_data:
                # Convert existing age_hours to minutes
                return float(token_data['age_hours']) * 60

            if not timestamp:
                # Default to assuming it's been around for a while
                return 60.0  # 1 hour default

            # Parse timestamp
            if isinstance(timestamp, (int, float)):
                # Unix timestamp (check if milliseconds)
                if timestamp > 1e12:
                    timestamp = timestamp / 1000
                created_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            else:
                # ISO string
                created_time = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))

            # Calculate age
            now = datetime.now(timezone.utc)
            age = now - created_time
            return age.total_seconds() / 60

        except Exception as e:
            logger.debug(f"Error calculating pool age: {e}")
            return 60.0  # Default to 1 hour

    def _analyze_launch_window(self, pool_age_minutes: float) -> Tuple[float, str, bool]:
        """
        Analyze launch window timing

        Returns:
            (score: float 0-1, reason: str, in_golden_window: bool)
        """
        if pool_age_minutes < self.SNIPER_WINDOW:
            # Too early - snipers still active
            return 0.3, f"⚠️ Very early ({pool_age_minutes:.1f}m) - sniper window", False

        elif self.GOLDEN_WINDOW_START <= pool_age_minutes <= self.GOLDEN_WINDOW_END:
            # GOLDEN WINDOW - best time to enter
            return 1.0, f"🎯 GOLDEN WINDOW ({pool_age_minutes:.1f}m after launch)", True

        elif pool_age_minutes <= self.MOMENTUM_WINDOW_END:
            # Still has momentum but golden window passed
            return 0.7, f"Good timing ({pool_age_minutes:.1f}m after launch)", False

        elif pool_age_minutes <= 60:
            # Within first hour - some potential
            return 0.5, f"Fair timing ({pool_age_minutes:.1f}m after launch)", False

        elif pool_age_minutes <= 360:  # 6 hours
            # Established token
            return 0.3, f"Established token ({pool_age_minutes/60:.1f}h old)", False

        else:
            # Old token - not a launch play
            hours = pool_age_minutes / 60
            if hours < 24:
                return 0.2, f"Old token ({hours:.1f}h old)", False
            else:
                days = hours / 24
                return 0.1, f"Very old token ({days:.1f}d old)", False

    def _analyze_time_of_day(self) -> Tuple[float, str]:
        """
        Analyze current time of day for trading

        Returns:
            (score: float 0-1, reason: str)
        """
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour

        if self.US_TRADING_START <= hour <= self.US_TRADING_END:
            # US trading hours (highest volume)
            return 1.0, f"🇺🇸 US trading hours ({hour:02d}:00 UTC)"

        elif 10 <= hour < self.US_TRADING_START:
            # EU trading hours (medium volume)
            return 0.7, f"🇪🇺 EU trading hours ({hour:02d}:00 UTC)"

        elif self.ASIA_TRADING_START <= hour < self.ASIA_TRADING_END:
            # Asia trading hours (lowest volume)
            return 0.3, f"🇯🇵 Asia trading hours ({hour:02d}:00 UTC) - low volume"

        else:
            # Between EU and Asia (low volume)
            return 0.5, f"Off-peak hours ({hour:02d}:00 UTC)"

    def _analyze_day_of_week(self) -> Tuple[float, str]:
        """
        Analyze day of week patterns

        Returns:
            (score: float 0-1, reason: str)
        """
        now = datetime.now(timezone.utc)
        day = now.weekday()  # 0=Monday, 6=Sunday

        if day in [0, 1, 2, 3]:  # Monday-Thursday
            # Best trading days
            return 1.0, ""  # Don't mention if good

        elif day == 4:  # Friday
            # Good but lower volume towards evening
            return 0.8, "Friday (volume drops in afternoon)"

        elif day == 5:  # Saturday
            # Weekend - lower volume
            return 0.5, "⚠️ Saturday - lower weekend volume"

        elif day == 6:  # Sunday
            # Worst day - very low volume
            return 0.4, "⚠️ Sunday - lowest volume day"

        return 0.7, ""

    def should_wait_for_better_timing(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Determine if we should wait for better timing

        Returns:
            (should_wait: bool, reason: str)
        """
        timing = self.analyze_timing(token_data)

        # Never wait if in golden window
        if timing['in_golden_window']:
            return False, "In golden window - trade now!"

        # Wait if pool is too young (sniper zone)
        if timing['pool_age_minutes'] < self.SNIPER_WINDOW:
            wait_seconds = (self.SNIPER_WINDOW - timing['pool_age_minutes']) * 60
            return True, f"Wait {wait_seconds:.0f}s for snipers to settle"

        # Wait if pool is too old (momentum expired)
        if timing['pool_age_minutes'] > self.MOMENTUM_WINDOW_END:
            return True, f"Launch momentum expired ({timing['pool_age_minutes']:.1f}m old)"

        # Don't wait during good trading hours with decent timing
        if timing['timing_score'] >= 0.6:
            return False, f"Good timing (score: {timing['timing_score']:.2f})"

        # Wait if terrible timing
        if timing['timing_score'] < 0.3:
            return True, f"Poor timing (score: {timing['timing_score']:.2f}) - {', '.join(timing['warnings'])}"

        # Otherwise, proceed
        return False, f"Fair timing (score: {timing['timing_score']:.2f})"

    def _empty_timing(self) -> Dict:
        """Return empty timing data"""
        return {
            'timing_score': 0.5,
            'timing_rating': "UNKNOWN",
            'in_golden_window': False,
            'pool_age_minutes': 0,
            'time_of_day_score': 0.5,
            'day_of_week_score': 0.5,
            'reasons': ["Timing data unavailable"],
            'warnings': []
        }
