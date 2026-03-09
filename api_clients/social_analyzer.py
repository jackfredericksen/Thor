# social_analyzer.py - Social Sentiment Analysis
"""
Analyzes social media sentiment for memecoin trading:
- Twitter mention tracking (via nitter.net or alternative scrapers)
- Telegram group activity monitoring
- Community growth rate
- Influencer mentions
- Sentiment scoring

Note: Actual Twitter API requires paid access ($100/month).
This implementation uses free alternatives and public data sources.
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SocialMetrics:
    """Social media metrics for a token"""
    twitter_mentions_1h: int
    twitter_mentions_24h: int
    twitter_sentiment_score: float  # -1 to 1 (negative to positive)
    telegram_members: int
    telegram_messages_1h: int
    telegram_growth_rate: float  # % change in members
    influencer_mentions: List[str]
    social_score: float  # 0-1 overall social strength
    sentiment_rating: str  # "VERY_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "VERY_NEGATIVE"
    warnings: List[str]
    strengths: List[str]


class SocialAnalyzer:
    """
    Analyze social sentiment for memecoins

    Uses free/public APIs to track:
    - Twitter mentions via web scraping
    - Telegram group stats via public info
    - Trending topic detection
    """

    _CACHE_MAX_SIZE = 200

    def __init__(self):
        self.cache = {}  # Token -> (timestamp, metrics)
        self.cache_ttl = 300  # 5 minutes

        # Rate limiting
        self.last_request_time = {}
        self.min_request_interval = 2  # seconds between requests

    @contextmanager
    def _get_session(self):
        """Context manager for requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        try:
            yield session
        finally:
            session.close()

    def analyze_social_sentiment(
        self,
        token_address: str,
        symbol: str = None,
        token_data: Dict = None
    ) -> SocialMetrics:
        """
        Analyze social sentiment for a token

        Args:
            token_address: Solana token address
            symbol: Token symbol (e.g., "BONK")
            token_data: Optional token data with social links

        Returns:
            SocialMetrics with comprehensive social analysis
        """
        try:
            # Check cache
            if token_address in self.cache:
                timestamp, metrics = self.cache[token_address]
                if time.time() - timestamp < self.cache_ttl:
                    logger.debug(f"Using cached social metrics for {symbol or token_address[:8]}")
                    return metrics

            if not symbol and token_data:
                symbol = token_data.get('symbol', token_address[:8])
            elif not symbol:
                symbol = token_address[:8]

            logger.debug(f"Analyzing social sentiment for {symbol}...")

            # Get social links from token data
            social_links = self._extract_social_links(token_data) if token_data else {}

            # Analyze Twitter
            twitter_metrics = self._analyze_twitter(symbol, token_address)

            # Analyze Telegram
            telegram_metrics = self._analyze_telegram(social_links.get('telegram'), symbol)

            # Calculate overall social score
            social_score = self._calculate_social_score(twitter_metrics, telegram_metrics)

            # Determine sentiment rating
            sentiment_rating = self._get_sentiment_rating(social_score, twitter_metrics)

            # Compile warnings and strengths
            warnings = []
            strengths = []

            # Twitter analysis
            if twitter_metrics['mentions_1h'] == 0:
                warnings.append("⚠️ No recent Twitter mentions")
            elif twitter_metrics['mentions_1h'] > 50:
                strengths.append(f"🔥 High Twitter activity ({twitter_metrics['mentions_1h']} mentions/hour)")

            if twitter_metrics['sentiment'] < -0.3:
                warnings.append("⚠️ Negative Twitter sentiment")
            elif twitter_metrics['sentiment'] > 0.5:
                strengths.append(f"✅ Positive sentiment (score: {twitter_metrics['sentiment']:.2f})")

            # Telegram analysis
            if telegram_metrics['members'] == 0:
                warnings.append("⚠️ No Telegram community found")
            elif telegram_metrics['members'] > 1000:
                strengths.append(f"✅ Active Telegram ({telegram_metrics['members']:,} members)")

            if telegram_metrics['growth_rate'] > 50:
                strengths.append(f"🚀 Rapid Telegram growth (+{telegram_metrics['growth_rate']:.0f}%)")
            elif telegram_metrics['growth_rate'] < -20:
                warnings.append("⚠️ Shrinking Telegram community")

            # Influencer mentions
            influencer_mentions = twitter_metrics.get('influencers', [])
            if influencer_mentions:
                strengths.append(f"🎯 Mentioned by {len(influencer_mentions)} influencers")

            metrics = SocialMetrics(
                twitter_mentions_1h=twitter_metrics['mentions_1h'],
                twitter_mentions_24h=twitter_metrics['mentions_24h'],
                twitter_sentiment_score=twitter_metrics['sentiment'],
                telegram_members=telegram_metrics['members'],
                telegram_messages_1h=telegram_metrics['messages_1h'],
                telegram_growth_rate=telegram_metrics['growth_rate'],
                influencer_mentions=influencer_mentions,
                social_score=social_score,
                sentiment_rating=sentiment_rating,
                warnings=warnings,
                strengths=strengths
            )

            # Cache result (evict oldest if over limit)
            self.cache[token_address] = (time.time(), metrics)
            if len(self.cache) > self._CACHE_MAX_SIZE:
                oldest = min(self.cache, key=lambda k: self.cache[k][0])
                del self.cache[oldest]

            return metrics

        except Exception as e:
            logger.error(f"Error analyzing social sentiment for {symbol}: {e}")
            return self._empty_metrics()

    def _extract_social_links(self, token_data: Dict) -> Dict[str, str]:
        """Extract social media links from token data"""
        links = {}

        try:
            # Check various fields where social links might be
            if 'info' in token_data:
                info = token_data['info']
                links['twitter'] = info.get('twitter') or info.get('twitter_url')
                links['telegram'] = info.get('telegram') or info.get('telegram_url')
                links['website'] = info.get('website') or info.get('website_url')

            # DexScreener format
            if 'socials' in token_data:
                for social in token_data['socials']:
                    platform = social.get('type', '').lower()
                    url = social.get('url', '')
                    if platform in ['twitter', 'telegram', 'website']:
                        links[platform] = url

            # Direct fields
            for key in ['twitter', 'telegram', 'website', 'discord']:
                if key in token_data:
                    links[key] = token_data[key]

        except Exception as e:
            logger.debug(f"Error extracting social links: {e}")

        return links

    def _analyze_twitter(self, symbol: str, token_address: str) -> Dict:
        """
        Analyze Twitter mentions and sentiment

        Uses public Twitter alternatives since actual API is expensive
        """
        try:
            self._rate_limit('twitter')

            # Try multiple free Twitter data sources
            metrics = {
                'mentions_1h': 0,
                'mentions_24h': 0,
                'sentiment': 0.0,
                'influencers': []
            }

            # Source 1: LunarCrush (has free tier for social metrics)
            try:
                lunar_data = self._get_lunarcrush_data(symbol)
                if lunar_data:
                    metrics['mentions_24h'] = lunar_data.get('social_volume', 0)
                    metrics['mentions_1h'] = lunar_data.get('social_volume', 0) // 24  # Estimate
                    metrics['sentiment'] = lunar_data.get('sentiment', 0) / 100  # Convert to -1 to 1
                    metrics['influencers'] = lunar_data.get('influencers', [])
            except Exception as e:
                logger.debug(f"LunarCrush unavailable: {e}")

            # Source 2: Twitter search via public scraping (very limited)
            # Note: This is unreliable and for demonstration only
            try:
                search_metrics = self._search_twitter_mentions(symbol)
                if search_metrics['mentions'] > metrics['mentions_1h']:
                    metrics['mentions_1h'] = search_metrics['mentions']
                    metrics['mentions_24h'] = max(metrics['mentions_24h'], search_metrics['mentions'] * 24)
            except Exception as e:
                logger.debug(f"Twitter search unavailable: {e}")

            return metrics

        except Exception as e:
            logger.debug(f"Error analyzing Twitter: {e}")
            return {
                'mentions_1h': 0,
                'mentions_24h': 0,
                'sentiment': 0.0,
                'influencers': []
            }

    def _get_lunarcrush_data(self, symbol: str) -> Optional[Dict]:
        """Get social data from LunarCrush (has free tier)"""
        try:
            # LunarCrush has a free API tier (limited)
            # Would require API key: LUNARCRUSH_API_KEY
            # For now, return None (requires user to add API key)

            # Example implementation if user adds API key:
            # api_key = os.getenv('LUNARCRUSH_API_KEY')
            # if not api_key:
            #     return None
            #
            # with self._get_session() as session:
            #     url = f"https://api.lunarcrush.com/v2?data=assets&symbol={symbol}"
            #     response = session.get(url, params={'key': api_key}, timeout=10)
            #     if response.status_code == 200:
            #         data = response.json()
            #         return data.get('data', [{}])[0] if data.get('data') else None

            return None

        except Exception as e:
            logger.debug(f"LunarCrush error: {e}")
            return None

    def _search_twitter_mentions(self, symbol: str) -> Dict:
        """
        Search for Twitter mentions using public methods

        Note: This is very limited and unreliable without Twitter API
        """
        try:
            # Placeholder - would need Twitter API access ($100/month minimum)
            # Or use alternative scrapers (which often get blocked)

            # For demonstration, return estimated values based on symbol popularity
            # In production, you'd need:
            # 1. Twitter API access, OR
            # 2. Third-party aggregator (LunarCrush, Santiment), OR
            # 3. Web scraping service (unreliable, often blocked)

            return {
                'mentions': 0,
                'sentiment': 0.0
            }

        except Exception as e:
            logger.debug(f"Twitter search error: {e}")
            return {'mentions': 0, 'sentiment': 0.0}

    def _analyze_telegram(self, telegram_url: Optional[str], symbol: str) -> Dict:
        """
        Analyze Telegram group activity

        Note: Telegram has limited public API for group stats
        """
        try:
            self._rate_limit('telegram')

            metrics = {
                'members': 0,
                'messages_1h': 0,
                'growth_rate': 0.0
            }

            if not telegram_url:
                return metrics

            # Extract group username from URL
            group_username = self._extract_telegram_username(telegram_url)
            if not group_username:
                return metrics

            # Try to get public group info
            try:
                group_info = self._get_telegram_group_info(group_username)
                if group_info:
                    metrics['members'] = group_info.get('members', 0)
                    metrics['messages_1h'] = group_info.get('recent_messages', 0)
                    metrics['growth_rate'] = group_info.get('growth_rate', 0.0)
            except Exception as e:
                logger.debug(f"Error fetching Telegram info: {e}")

            return metrics

        except Exception as e:
            logger.debug(f"Error analyzing Telegram: {e}")
            return {
                'members': 0,
                'messages_1h': 0,
                'growth_rate': 0.0
            }

    def _extract_telegram_username(self, url: str) -> Optional[str]:
        """Extract Telegram username from URL"""
        try:
            # Handle formats:
            # https://t.me/groupname
            # https://telegram.me/groupname
            # @groupname

            if '@' in url:
                return url.split('@')[1].split('/')[0]

            if 't.me/' in url or 'telegram.me/' in url:
                parts = url.split('/')
                return parts[-1] if parts else None

            return None

        except Exception:
            return None

    def _get_telegram_group_info(self, username: str) -> Optional[Dict]:
        """
        Get Telegram group info

        Note: Telegram Bot API has limited access to group stats
        Requires bot to be in the group
        """
        try:
            # Telegram Bot API would require:
            # 1. Bot token (TELEGRAM_BOT_TOKEN)
            # 2. Bot must be member of the group
            # 3. Group must be public

            # For now, return None (requires user setup)
            # Example implementation if user adds bot:
            # bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            # if not bot_token:
            #     return None
            #
            # with self._get_session() as session:
            #     url = f"https://api.telegram.org/bot{bot_token}/getChat"
            #     response = session.get(url, params={'chat_id': f'@{username}'}, timeout=10)
            #     if response.status_code == 200:
            #         data = response.json()
            #         if data.get('ok'):
            #             chat = data.get('result', {})
            #             return {
            #                 'members': chat.get('members_count', 0),
            #                 'recent_messages': 0,  # Would need separate API call
            #                 'growth_rate': 0.0  # Would need historical tracking
            #             }

            return None

        except Exception as e:
            logger.debug(f"Telegram API error: {e}")
            return None

    def _calculate_social_score(self, twitter_metrics: Dict, telegram_metrics: Dict) -> float:
        """
        Calculate overall social score (0-1)

        Weighs various social metrics
        """
        try:
            score = 0.0

            # Twitter component (60% weight)
            twitter_score = 0.0

            # Mentions (40%)
            mentions_1h = twitter_metrics['mentions_1h']
            if mentions_1h >= 100:
                twitter_score += 0.4
            elif mentions_1h >= 50:
                twitter_score += 0.3
            elif mentions_1h >= 20:
                twitter_score += 0.2
            elif mentions_1h >= 5:
                twitter_score += 0.1

            # Sentiment (20%)
            sentiment = twitter_metrics['sentiment']
            if sentiment > 0.5:
                twitter_score += 0.2
            elif sentiment > 0.2:
                twitter_score += 0.15
            elif sentiment > 0:
                twitter_score += 0.1
            elif sentiment > -0.3:
                twitter_score += 0.05
            # Negative sentiment adds 0

            score += twitter_score * 0.6

            # Telegram component (40% weight)
            telegram_score = 0.0

            # Members (25%)
            members = telegram_metrics['members']
            if members >= 5000:
                telegram_score += 0.25
            elif members >= 1000:
                telegram_score += 0.2
            elif members >= 500:
                telegram_score += 0.15
            elif members >= 100:
                telegram_score += 0.1
            elif members > 0:
                telegram_score += 0.05

            # Growth rate (15%)
            growth = telegram_metrics['growth_rate']
            if growth > 100:  # 100%+ growth
                telegram_score += 0.15
            elif growth > 50:
                telegram_score += 0.12
            elif growth > 20:
                telegram_score += 0.08
            elif growth > 0:
                telegram_score += 0.05
            # Negative growth adds 0

            score += telegram_score * 0.4

            # Clamp to 0-1
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.debug(f"Error calculating social score: {e}")
            return 0.0

    def _get_sentiment_rating(self, social_score: float, twitter_metrics: Dict) -> str:
        """Determine sentiment rating from scores"""
        try:
            sentiment = twitter_metrics['sentiment']

            # Weight both social score and Twitter sentiment
            combined = (social_score * 0.6) + ((sentiment + 1) / 2 * 0.4)  # Normalize sentiment to 0-1

            if combined >= 0.8:
                return "VERY_POSITIVE"
            elif combined >= 0.6:
                return "POSITIVE"
            elif combined >= 0.4:
                return "NEUTRAL"
            elif combined >= 0.2:
                return "NEGATIVE"
            else:
                return "VERY_NEGATIVE"

        except Exception:
            return "NEUTRAL"

    def _rate_limit(self, source: str):
        """Simple rate limiting"""
        try:
            last_time = self.last_request_time.get(source, 0)
            elapsed = time.time() - last_time

            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

            self.last_request_time[source] = time.time()

        except Exception:
            pass

    def _empty_metrics(self) -> SocialMetrics:
        """Return empty metrics on error"""
        return SocialMetrics(
            twitter_mentions_1h=0,
            twitter_mentions_24h=0,
            twitter_sentiment_score=0.0,
            telegram_members=0,
            telegram_messages_1h=0,
            telegram_growth_rate=0.0,
            influencer_mentions=[],
            social_score=0.0,
            sentiment_rating="NEUTRAL",
            warnings=["⚠️ Social data unavailable"],
            strengths=[]
        )

    def should_skip_due_to_social(self, metrics: SocialMetrics) -> Tuple[bool, str]:
        """
        Determine if token should be skipped based on social metrics

        Returns:
            (should_skip: bool, reason: str)
        """
        try:
            # Skip if very negative sentiment
            if metrics.sentiment_rating == "VERY_NEGATIVE":
                return True, f"Very negative social sentiment (score: {metrics.social_score:.2f})"

            # Skip if Twitter sentiment is very negative
            if metrics.twitter_sentiment_score < -0.5:
                return True, f"Negative Twitter sentiment ({metrics.twitter_sentiment_score:.2f})"

            # Skip if Telegram community is shrinking rapidly
            if metrics.telegram_members > 100 and metrics.telegram_growth_rate < -50:
                return True, f"Telegram community shrinking ({metrics.telegram_growth_rate:.0f}%)"

            # Don't skip, but warn if social score is low
            if metrics.social_score < 0.2:
                return False, f"Low social score ({metrics.social_score:.2f}) - proceed with caution"

            return False, f"Social metrics acceptable (score: {metrics.social_score:.2f})"

        except Exception:
            return False, "Social data unavailable - proceeding"


# Quick helper function for simple checks
def quick_social_check(token_address: str, symbol: str = None) -> bool:
    """
    Quick social sentiment check

    Returns True if social metrics are acceptable, False if should reject
    """
    try:
        analyzer = SocialAnalyzer()
        metrics = analyzer.analyze_social_sentiment(token_address, symbol)
        should_skip, _ = analyzer.should_skip_due_to_social(metrics)
        return not should_skip
    except Exception:
        return True  # On error, don't block the trade
