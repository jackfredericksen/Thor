"""
Token Contract Analysis - Honeypot & Rug Detection
Analyzes Solana token contracts for dangerous patterns
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
import base58

logger = logging.getLogger(__name__)


class TokenAnalyzer:
    """Analyze token contracts for safety risks"""

    def __init__(self, rpc_url: str):
        self.client = AsyncClient(rpc_url)

    async def analyze_token(self, token_mint: str) -> Dict:
        """
        Comprehensive token safety analysis

        Returns:
            Dict with safety scores and flags
        """
        try:
            mint_pubkey = Pubkey.from_string(token_mint)

            # Run all checks in parallel
            results = await asyncio.gather(
                self.check_mint_authority(mint_pubkey),
                self.check_freeze_authority(mint_pubkey),
                self.check_token_supply(mint_pubkey),
                self.check_top_holders(token_mint),
                return_exceptions=True
            )

            has_mint_authority = results[0] if not isinstance(results[0], Exception) else None
            has_freeze_authority = results[1] if not isinstance(results[1], Exception) else None
            supply_info = results[2] if not isinstance(results[2], Exception) else {}
            holder_info = results[3] if not isinstance(results[3], Exception) else {}

            # Calculate safety score (0-100)
            safety_score = 100
            flags = []

            # Mint authority check (-40 points if exists)
            if has_mint_authority:
                safety_score -= 40
                flags.append("mint_authority_exists")
                logger.warning(f"Token {token_mint[:8]} has mint authority - can create infinite tokens")

            # Freeze authority check (-30 points if exists)
            if has_freeze_authority:
                safety_score -= 30
                flags.append("freeze_authority_exists")
                logger.warning(f"Token {token_mint[:8]} has freeze authority - can freeze wallets")

            # Supply concentration check
            top_holder_pct = holder_info.get('top_holder_percentage', 0)
            if top_holder_pct > 50:
                safety_score -= 20
                flags.append("high_concentration")
                logger.warning(f"Token {token_mint[:8]} has {top_holder_pct:.1f}% held by top holder")
            elif top_holder_pct > 30:
                safety_score -= 10
                flags.append("medium_concentration")

            # Small holder count check
            holder_count = holder_info.get('holder_count', 0)
            if holder_count < 10:
                safety_score -= 15
                flags.append("few_holders")

            return {
                'is_safe': safety_score >= 50,
                'safety_score': max(0, safety_score),
                'has_mint_authority': has_mint_authority,
                'has_freeze_authority': has_freeze_authority,
                'supply_info': supply_info,
                'holder_info': holder_info,
                'flags': flags,
                'recommendation': self._get_recommendation(safety_score, flags)
            }

        except Exception as e:
            logger.error(f"Error analyzing token {token_mint}: {e}")
            return {
                'is_safe': False,
                'safety_score': 0,
                'error': str(e),
                'flags': ['analysis_failed'],
                'recommendation': 'AVOID - Analysis failed'
            }

    async def check_mint_authority(self, mint_pubkey: Pubkey) -> bool:
        """Check if mint authority still exists (bad sign)"""
        try:
            account_info = await self.client.get_account_info(mint_pubkey)

            if not account_info.value or not account_info.value.data:
                return None

            # Parse mint account data
            # Mint authority is at bytes 0-32 (if not None)
            data = account_info.value.data
            if len(data) < 82:  # Minimum mint account size
                return None

            # Check if mint authority is set (not all zeros)
            mint_authority = data[0:32]
            has_authority = any(b != 0 for b in mint_authority)

            return has_authority

        except Exception as e:
            logger.debug(f"Error checking mint authority: {e}")
            return None

    async def check_freeze_authority(self, mint_pubkey: Pubkey) -> bool:
        """Check if freeze authority exists (bad sign)"""
        try:
            account_info = await self.client.get_account_info(mint_pubkey)

            if not account_info.value or not account_info.value.data:
                return None

            data = account_info.value.data
            if len(data) < 82:
                return None

            # Freeze authority is at bytes 46-78
            # First byte (46) indicates if freeze authority exists
            has_freeze = data[46] == 1

            return has_freeze

        except Exception as e:
            logger.debug(f"Error checking freeze authority: {e}")
            return None

    async def check_token_supply(self, mint_pubkey: Pubkey) -> Dict:
        """Get token supply information"""
        try:
            supply_response = await self.client.get_token_supply(mint_pubkey)

            if supply_response.value:
                return {
                    'total_supply': int(supply_response.value.amount),
                    'decimals': supply_response.value.decimals,
                    'ui_amount': supply_response.value.ui_amount
                }

            return {}

        except Exception as e:
            logger.debug(f"Error checking token supply: {e}")
            return {}

    async def check_top_holders(self, token_mint: str) -> Dict:
        """
        Analyze holder distribution
        Note: This is simplified - full implementation would query all token accounts
        """
        try:
            mint_pubkey = Pubkey.from_string(token_mint)

            # Get largest token accounts
            response = await self.client.get_token_largest_accounts(mint_pubkey)

            if not response.value:
                return {}

            accounts = response.value
            if not accounts:
                return {}

            # Calculate distribution
            total = sum(int(acc.amount) for acc in accounts)
            if total == 0:
                return {}

            top_holder_amount = int(accounts[0].amount)
            top_holder_pct = (top_holder_amount / total) * 100

            return {
                'holder_count': len(accounts),  # This is partial - largest accounts only
                'top_holder_percentage': top_holder_pct,
                'top_5_percentage': sum(int(acc.amount) for acc in accounts[:5]) / total * 100
            }

        except Exception as e:
            logger.debug(f"Error checking top holders: {e}")
            return {}

    def _get_recommendation(self, safety_score: int, flags: List[str]) -> str:
        """Get trading recommendation based on analysis"""
        if safety_score >= 80:
            return "SAFE - Low risk"
        elif safety_score >= 60:
            return "CAUTION - Medium risk"
        elif safety_score >= 40:
            return "RISKY - Proceed with caution"
        else:
            return "AVOID - High risk of rug pull"

    async def quick_check(self, token_mint: str) -> bool:
        """
        Fast safety check - just critical flags

        Returns:
            True if token passes basic safety, False if dangerous
        """
        try:
            mint_pubkey = Pubkey.from_string(token_mint)

            # Only check mint and freeze authority (fast checks)
            has_mint = await self.check_mint_authority(mint_pubkey)
            has_freeze = await self.check_freeze_authority(mint_pubkey)

            # Fail if either exists
            if has_mint or has_freeze:
                return False

            return True

        except Exception as e:
            logger.debug(f"Quick check failed for {token_mint}: {e}")
            return False  # Fail safe - if we can't check, don't trade

    async def close(self):
        """Close RPC client"""
        await self.client.close()


class LiquidityAnalyzer:
    """Analyze liquidity pool safety"""

    def __init__(self, rpc_url: str):
        self.client = AsyncClient(rpc_url)

    async def check_lp_burned(self, pool_address: str) -> Tuple[bool, float]:
        """
        Check if LP tokens are burned (good sign)

        Returns:
            (is_burned, percentage_burned)
        """
        try:
            # This is simplified - would need to:
            # 1. Find LP token mint for this pool
            # 2. Check if LP tokens sent to burn address
            # 3. Calculate % burned

            # For now, return conservative estimate
            return (False, 0.0)

        except Exception as e:
            logger.debug(f"Error checking LP burn: {e}")
            return (False, 0.0)

    async def check_liquidity_locked(self, pool_address: str) -> Tuple[bool, Optional[int]]:
        """
        Check if liquidity is locked

        Returns:
            (is_locked, unlock_timestamp)
        """
        try:
            # Would need to check if LP tokens are in time-lock contract
            # This requires knowing the lock program address

            return (False, None)

        except Exception as e:
            logger.debug(f"Error checking liquidity lock: {e}")
            return (False, None)

    async def get_pool_liquidity(self, pool_address: str) -> Optional[float]:
        """Get current pool liquidity in USD"""
        try:
            # Would need to:
            # 1. Get pool account data
            # 2. Parse reserves
            # 3. Calculate USD value

            return None

        except Exception as e:
            logger.debug(f"Error getting pool liquidity: {e}")
            return None

    async def close(self):
        """Close RPC client"""
        await self.client.close()
