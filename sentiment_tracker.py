"""
Social Sentiment Tracker
Track Twitter/X mentions and sentiment for tokens
"""

import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SentimentData:
    """Sentiment analysis result"""
    token_symbol: str
    token_address: str
    sentiment_score: float  # -1 to 1
    mention_count: int
    positive_mentions: int
    negative_mentions: int
    neutral_mentions: int
    trending_score: float  # 0 to 1
    analyzed_at: datetime
    keywords: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class SentimentTracker:
    """Track social media sentiment for tokens"""

    def __init__(self, twitter_bearer_token: Optional[str] = None):
        self.twitter_bearer_token = twitter_bearer_token
        self.sentiment_cache: Dict[str, SentimentData] = {}
        self.cache_duration_minutes = 10

    async def analyze_token_sentiment(
        self,
        token_symbol: str,
        token_address: str = None
    ) -> Optional[SentimentData]:
        """
        Analyze sentiment for a token

        Args:
            token_symbol: Token symbol (e.g., BONK, PEPE)
            token_address: Optional token address

        Returns:
            SentimentData or None
        """
        # Check cache first
        cache_key = f"{token_symbol}_{token_address}"
        if cache_key in self.sentiment_cache:
            cached = self.sentiment_cache[cache_key]
            age = (datetime.now() - cached.analyzed_at).total_seconds() / 60

            if age < self.cache_duration_minutes:
                logger.debug(f"Using cached sentiment for {token_symbol}")
                return cached

        try:
            # Gather sentiment from multiple sources
            twitter_sentiment = await self._get_twitter_sentiment(token_symbol)
            reddit_sentiment = await self._get_reddit_sentiment(token_symbol)

            # Combine sentiments
            combined_sentiment = self._combine_sentiments([
                twitter_sentiment,
                reddit_sentiment
            ])

            if combined_sentiment:
                # Cache result
                self.sentiment_cache[cache_key] = combined_sentiment
                return combined_sentiment

            return None

        except Exception as e:
            logger.error(f"Error analyzing sentiment for {token_symbol}: {e}")
            return None

    async def _get_twitter_sentiment(self, token_symbol: str) -> Optional[Dict]:
        """
        Get sentiment from Twitter/X

        Uses Twitter API v2 to search recent tweets
        """
        if not self.twitter_bearer_token:
            logger.debug("Twitter API token not configured")
            return None

        try:
            # Search for tweets mentioning token
            search_query = f"${token_symbol} OR #{token_symbol} -is:retweet lang:en"

            headers = {
                'Authorization': f'Bearer {self.twitter_bearer_token}'
            }

            params = {
                'query': search_query,
                'max_results': 100,
                'tweet.fields': 'created_at,public_metrics,text'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.twitter.com/2/tweets/search/recent',
                    headers=headers,
                    params=params
                ) as response:

                    if response.status != 200:
                        logger.error(f"Twitter API error: {response.status}")
                        return None

                    data = await response.json()
                    tweets = data.get('data', [])

                    if not tweets:
                        return None

                    # Analyze tweet sentiment
                    positive = 0
                    negative = 0
                    neutral = 0

                    trending_score = 0
                    keywords = []

                    for tweet in tweets:
                        text = tweet.get('text', '').lower()

                        # Simple sentiment analysis based on keywords
                        # Production would use ML model or sentiment API
                        if any(word in text for word in ['moon', 'bullish', 'buy', 'gem', 'pump', 'rocket', '🚀']):
                            positive += 1
                        elif any(word in text for word in ['dump', 'rug', 'scam', 'bearish', 'sell']):
                            negative += 1
                        else:
                            neutral += 1

                        # Track engagement
                        metrics = tweet.get('public_metrics', {})
                        likes = metrics.get('like_count', 0)
                        retweets = metrics.get('retweet_count', 0)
                        trending_score += (likes + retweets * 2)

                    # Normalize trending score
                    trending_score = min(trending_score / 10000, 1.0)

                    return {
                        'source': 'twitter',
                        'mention_count': len(tweets),
                        'positive': positive,
                        'negative': negative,
                        'neutral': neutral,
                        'trending_score': trending_score,
                        'keywords': keywords
                    }

        except Exception as e:
            logger.error(f"Error fetching Twitter sentiment: {e}")
            return None

    async def _get_reddit_sentiment(self, token_symbol: str) -> Optional[Dict]:
        """
        Get sentiment from Reddit

        Uses Reddit API (no auth needed for public posts)
        """
        try:
            # Search relevant crypto subreddits
            subreddits = ['CryptoMoonShots', 'SatoshiStreetBets', 'CryptoCurrency']

            all_mentions = []

            async with aiohttp.ClientSession() as session:
                for subreddit in subreddits:
                    url = f'https://www.reddit.com/r/{subreddit}/search.json'
                    params = {
                        'q': token_symbol,
                        'restrict_sr': 'on',
                        'sort': 'new',
                        'limit': 25
                    }

                    headers = {
                        'User-Agent': 'Mozilla/5.0'
                    }

                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            posts = data.get('data', {}).get('children', [])
                            all_mentions.extend(posts)

            if not all_mentions:
                return None

            # Analyze sentiment
            positive = 0
            negative = 0
            neutral = 0
            trending_score = 0

            for post in all_mentions:
                post_data = post.get('data', {})
                title = post_data.get('title', '').lower()
                selftext = post_data.get('selftext', '').lower()
                text = f"{title} {selftext}"

                # Simple sentiment
                if any(word in text for word in ['bullish', 'moon', 'buy', 'gem']):
                    positive += 1
                elif any(word in text for word in ['bearish', 'dump', 'scam', 'rug']):
                    negative += 1
                else:
                    neutral += 1

                # Engagement
                score = post_data.get('score', 0)
                comments = post_data.get('num_comments', 0)
                trending_score += (score + comments * 2)

            trending_score = min(trending_score / 1000, 1.0)

            return {
                'source': 'reddit',
                'mention_count': len(all_mentions),
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'trending_score': trending_score,
                'keywords': []
            }

        except Exception as e:
            logger.error(f"Error fetching Reddit sentiment: {e}")
            return None

    def _combine_sentiments(self, sentiments: List[Optional[Dict]]) -> Optional[SentimentData]:
        """Combine sentiment data from multiple sources"""
        # Filter out None values
        valid_sentiments = [s for s in sentiments if s is not None]

        if not valid_sentiments:
            return None

        # Aggregate data
        total_mentions = sum(s['mention_count'] for s in valid_sentiments)
        total_positive = sum(s['positive'] for s in valid_sentiments)
        total_negative = sum(s['negative'] for s in valid_sentiments)
        total_neutral = sum(s['neutral'] for s in valid_sentiments)

        # Calculate weighted sentiment score
        if total_mentions > 0:
            sentiment_score = (total_positive - total_negative) / total_mentions
        else:
            sentiment_score = 0.0

        # Average trending score
        avg_trending = sum(s['trending_score'] for s in valid_sentiments) / len(valid_sentiments)

        # Combine keywords
        all_keywords = []
        for s in valid_sentiments:
            all_keywords.extend(s.get('keywords', []))

        return SentimentData(
            token_symbol="<token_symbol>",
            token_address="<token_address>",
            sentiment_score=sentiment_score,
            mention_count=total_mentions,
            positive_mentions=total_positive,
            negative_mentions=total_negative,
            neutral_mentions=total_neutral,
            trending_score=avg_trending,
            analyzed_at=datetime.now(),
            keywords=list(set(all_keywords))[:10]  # Top 10 unique keywords
        )

    def get_sentiment_rating(self, sentiment_score: float) -> str:
        """Convert sentiment score to rating"""
        if sentiment_score >= 0.5:
            return "Very Bullish"
        elif sentiment_score >= 0.2:
            return "Bullish"
        elif sentiment_score >= -0.2:
            return "Neutral"
        elif sentiment_score >= -0.5:
            return "Bearish"
        else:
            return "Very Bearish"

    def should_trade_based_on_sentiment(
        self,
        sentiment_data: SentimentData,
        min_sentiment: float = 0.2,
        min_mentions: int = 10
    ) -> bool:
        """
        Determine if token should be traded based on sentiment

        Args:
            sentiment_data: Sentiment analysis result
            min_sentiment: Minimum sentiment score (-1 to 1)
            min_mentions: Minimum number of mentions

        Returns:
            True if sentiment supports trading
        """
        if sentiment_data.mention_count < min_mentions:
            logger.debug(f"Not enough mentions: {sentiment_data.mention_count} < {min_mentions}")
            return False

        if sentiment_data.sentiment_score < min_sentiment:
            logger.debug(f"Sentiment too low: {sentiment_data.sentiment_score:.2f} < {min_sentiment}")
            return False

        logger.info(
            f"Sentiment check passed: "
            f"{sentiment_data.mention_count} mentions, "
            f"score: {sentiment_data.sentiment_score:.2f} "
            f"({self.get_sentiment_rating(sentiment_data.sentiment_score)})"
        )

        return True

    async def batch_analyze_tokens(
        self,
        token_symbols: List[str]
    ) -> Dict[str, SentimentData]:
        """Analyze sentiment for multiple tokens in parallel"""
        tasks = [
            self.analyze_token_sentiment(symbol)
            for symbol in token_symbols
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Map results to symbols
        sentiment_map = {}
        for symbol, result in zip(token_symbols, results):
            if isinstance(result, SentimentData):
                sentiment_map[symbol] = result

        return sentiment_map

    def get_trending_tokens(
        self,
        min_trending_score: float = 0.5
    ) -> List[SentimentData]:
        """Get tokens with high trending scores from cache"""
        trending = [
            sentiment for sentiment in self.sentiment_cache.values()
            if sentiment.trending_score >= min_trending_score
        ]

        # Sort by trending score
        trending.sort(key=lambda x: x.trending_score, reverse=True)

        return trending


class SimpleSentimentAnalyzer:
    """
    Simplified sentiment analyzer without API dependencies

    Uses public data sources that don't require authentication
    """

    async def analyze_token(self, token_symbol: str) -> Optional[float]:
        """
        Simple sentiment score based on available metrics

        Returns:
            Sentiment score -1 to 1, or None
        """
        try:
            # This is a simplified version that could:
            # 1. Scrape CoinGecko community score
            # 2. Check DexScreener social links
            # 3. Analyze GitHub activity for tokens with repos
            # 4. Check for red flags in token description

            # Placeholder implementation
            logger.debug(f"Simplified sentiment analysis for {token_symbol}")

            # Would return actual score from analysis
            return 0.0

        except Exception as e:
            logger.error(f"Error in simple sentiment analysis: {e}")
            return None
