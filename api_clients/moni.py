# api_clients/moni.py
import logging
from typing import Any, Dict, List, Optional

import requests

from utils.base_client import BaseAPIClient
from utils.error_handling import validate_token_address

# Import config properly - this is the fix!
try:
    from config import config
except ImportError:
    # Fallback config if import fails
    class FallbackConfig:
        API_URLS = {"moni": "https://api.moni.score/v1/tokens"}
        API_KEYS = {"moni": ""}
        RATE_LIMITS = {"moni": 30}

    config = FallbackConfig()

logger = logging.getLogger(__name__)


class MoniClient(BaseAPIClient):
    """Moni API client for social sentiment analysis"""

    def __init__(self):
        super().__init__(
            base_url=config.API_URLS["moni"],
            api_key=config.API_KEYS.get("moni"),
            service_name="moni",
            requests_per_minute=config.RATE_LIMITS["moni"],
        )
        self.enabled = bool(config.API_KEYS.get("moni"))

    def get_sentiment(self, token_address: str) -> Dict[str, Any]:
        """
        Get social sentiment analysis for a token
        Requires Moni API subscription ($99+/month)
        """
        if not self.enabled:
            logger.warning("Moni API key not provided - sentiment analysis disabled")
            return {
                "token_address": token_address,
                "status": "disabled",
                "message": "Moni API subscription required for sentiment analysis",
                "sentiment_score": 0,
                "social_metrics": {},
            }

        if not validate_token_address(token_address):
            return {
                "token_address": token_address,
                "status": "error",
                "message": "Invalid token address",
                "sentiment_score": 0,
                "social_metrics": {},
            }

        try:
            # Make API call to Moni
            response = self.get(f"tokens/{token_address}/sentiment")

            return self._process_sentiment_response(response, token_address)

        except Exception as e:
            logger.error(
                f"Moni sentiment analysis failed for {token_address}: {str(e)}"
            )
            return {
                "token_address": token_address,
                "status": "error",
                "message": str(e),
                "sentiment_score": 0,
                "social_metrics": {},
            }

    def get_social_metrics(self, token_address: str) -> Dict[str, Any]:
        """Get detailed social metrics for a token"""
        if not self.enabled:
            return {
                "token_address": token_address,
                "status": "disabled",
                "twitter_mentions": 0,
                "telegram_activity": 0,
                "discord_activity": 0,
                "overall_buzz": 0,
            }

        try:
            response = self.get(f"tokens/{token_address}/social")
            return self._process_social_response(response, token_address)

        except Exception as e:
            logger.error(f"Failed to get social metrics for {token_address}: {str(e)}")
            return {
                "token_address": token_address,
                "status": "error",
                "message": str(e),
            }

    def _process_sentiment_response(
        self, response: Dict, token_address: str
    ) -> Dict[str, Any]:
        """Process Moni sentiment API response"""
        try:
            return {
                "token_address": token_address,
                "status": "success",
                "sentiment_score": response.get("sentiment_score", 0),
                "social_metrics": response.get("social_metrics", {}),
                "twitter_sentiment": response.get("twitter_sentiment", 0),
                "telegram_sentiment": response.get("telegram_sentiment", 0),
                "overall_buzz": response.get("overall_buzz", 0),
                "raw_response": response,
            }
        except Exception as e:
            logger.error(f"Failed to process Moni sentiment response: {str(e)}")
            return {
                "token_address": token_address,
                "status": "error",
                "message": "Failed to process sentiment response",
                "sentiment_score": 0,
                "social_metrics": {},
            }

    def _process_social_response(
        self, response: Dict, token_address: str
    ) -> Dict[str, Any]:
        """Process Moni social metrics response"""
        try:
            return {
                "token_address": token_address,
                "status": "success",
                "twitter_mentions": response.get("twitter_mentions", 0),
                "telegram_activity": response.get("telegram_activity", 0),
                "discord_activity": response.get("discord_activity", 0),
                "overall_buzz": response.get("overall_buzz", 0),
                "trending_score": response.get("trending_score", 0),
                "raw_response": response,
            }
        except Exception as e:
            logger.error(f"Failed to process social response: {str(e)}")
            return {
                "token_address": token_address,
                "status": "error",
                "message": str(e),
            }

    def get_sentiment_score(self, token_address: str) -> float:
        """Get simplified sentiment score (0-100)"""
        try:
            sentiment_data = self.get_sentiment(token_address)
            return sentiment_data.get("sentiment_score", 0)
        except Exception as e:
            logger.error(f"Failed to get sentiment score for {token_address}: {str(e)}")
            return 0.0

    def health_check(self) -> bool:
        """Check Moni API health"""
        if not self.enabled:
            return False

        try:
            response = self.get("health")
            return response.get("status") == "ok"
        except Exception:
            return False
