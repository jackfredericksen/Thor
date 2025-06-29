# api_clients/rugcheck.py
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
        API_URLS = {"rugcheck": "https://api.rugcheck.xyz/v1/audit"}
        API_KEYS = {"rugcheck": ""}
        RATE_LIMITS = {"rugcheck": 10}

    config = FallbackConfig()

logger = logging.getLogger(__name__)


class RugcheckClient(BaseAPIClient):
    """RugCheck API client for token security analysis"""

    def __init__(self):
        super().__init__(
            base_url=config.API_URLS["rugcheck"],
            api_key=config.API_KEYS.get("rugcheck"),
            service_name="rugcheck",
            requests_per_minute=config.RATE_LIMITS["rugcheck"],
        )
        self.enabled = bool(config.API_KEYS.get("rugcheck"))

    def audit_token(self, token_address: str) -> Dict[str, Any]:
        """
        Audit a token for security issues
        Requires RugCheck API key
        """
        if not self.enabled:
            logger.warning("RugCheck API key not provided - security analysis disabled")
            return {
                "token_address": token_address,
                "status": "disabled",
                "message": "RugCheck API key required for security analysis",
                "score": 0,
                "risks": [],
            }

        if not validate_token_address(token_address):
            return {
                "token_address": token_address,
                "status": "error",
                "message": "Invalid token address",
                "score": 0,
                "risks": ["Invalid address format"],
            }

        try:
            # Make API call to RugCheck
            response = self.post(
                "audit",
                json_data={
                    "contract": token_address,
                    "chain": "solana",  # Assuming Solana, adjust as needed
                },
            )

            return self._process_audit_response(response, token_address)

        except Exception as e:
            logger.error(f"RugCheck audit failed for {token_address}: {str(e)}")
            return {
                "token_address": token_address,
                "status": "error",
                "message": str(e),
                "score": 0,
                "risks": ["API call failed"],
            }

    def _process_audit_response(
        self, response: Dict, token_address: str
    ) -> Dict[str, Any]:
        """Process RugCheck API response"""
        try:
            return {
                "token_address": token_address,
                "status": "success",
                "score": response.get("score", 0),
                "risks": response.get("risks", []),
                "analysis": response.get("analysis", {}),
                "raw_response": response,
            }
        except Exception as e:
            logger.error(f"Failed to process RugCheck response: {str(e)}")
            return {
                "token_address": token_address,
                "status": "error",
                "message": "Failed to process audit response",
                "score": 0,
                "risks": [],
            }

    def get_token_score(self, token_address: str) -> float:
        """Get simplified security score for a token (0-100)"""
        try:
            audit_result = self.audit_token(token_address)
            return audit_result.get("score", 0)
        except Exception as e:
            logger.error(f"Failed to get token score for {token_address}: {str(e)}")
            return 0.0

    def health_check(self) -> bool:
        """Check RugCheck API health"""
        if not self.enabled:
            return False

        try:
            # Try a simple API call to check health
            response = self.get("health")
            return response.get("status") == "ok"
        except Exception:
            return False
