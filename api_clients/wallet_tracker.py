"""
Wallet Tracker - Copy Trading System
Monitors profitable wallets and copies their trades
"""

import logging
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature
import aiohttp

logger = logging.getLogger(__name__)

# Known DEX program IDs on Solana
DEX_PROGRAM_IDS: Dict[str, str] = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium_amm_v4",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "jupiter_v6",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pumpfun",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "orca_whirlpool",
    "LBUZKhRxPF3XUpBCjp4YzTKgLe4eLDhZ83vTssEB6qMa": "meteora_dlmm",
    "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN": "meteora_dbc",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "raydium_clmm",
    "5quBtoiQqxF9Jv6KYKctB59NT3gtJD2Y65kdnB1Uev3h": "raydium_lp_v4",
}

# Wrapped SOL mint
WSOL_MINT = "So11111111111111111111111111111111111111112"
# USDC mint
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class WalletTracker:
    """Track and copy trades from successful wallets"""

    def __init__(self, rpc_url: str):
        self.client = AsyncClient(rpc_url)
        self.tracked_wallets: Dict[str, Dict] = {}
        self.seen_transactions: Set[str] = set()
        self.transaction_history: Dict[str, List[Dict]] = {}

    def add_wallet(
        self,
        wallet_address: str,
        nickname: str = None,
        auto_copy: bool = True,
        copy_percentage: float = 1.0
    ):
        """
        Add wallet to tracking list

        Args:
            wallet_address: Wallet to track
            nickname: Optional friendly name
            auto_copy: Whether to automatically copy trades
            copy_percentage: % of position size to copy (0.1 = 10%)
        """
        self.tracked_wallets[wallet_address] = {
            'address': wallet_address,
            'nickname': nickname or wallet_address[:8],
            'auto_copy': auto_copy,
            'copy_percentage': copy_percentage,
            'total_trades': 0,
            'successful_trades': 0,
            'total_profit': 0.0,
            'added_at': datetime.now()
        }
        logger.info(f"Now tracking wallet: {nickname or wallet_address[:8]}")

    def remove_wallet(self, wallet_address: str):
        """Remove wallet from tracking"""
        if wallet_address in self.tracked_wallets:
            nickname = self.tracked_wallets[wallet_address]['nickname']
            del self.tracked_wallets[wallet_address]
            logger.info(f"Stopped tracking: {nickname}")

    async def get_recent_transactions(
        self,
        wallet_address: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get recent transactions for a wallet

        Returns list of transaction data
        """
        try:
            wallet_pubkey = Pubkey.from_string(wallet_address)

            # Get signature list
            response = await self.client.get_signatures_for_address(
                wallet_pubkey,
                limit=limit
            )

            if not response.value:
                return []

            transactions = []
            for sig_info in response.value:
                sig_str = str(sig_info.signature)

                # Skip if already seen
                if sig_str in self.seen_transactions:
                    continue

                self.seen_transactions.add(sig_str)

                # Get full transaction details
                tx_details = await self._parse_transaction(sig_str)
                if tx_details:
                    transactions.append(tx_details)

            return transactions

        except Exception as e:
            logger.error(f"Error getting transactions for {wallet_address[:8]}: {e}")
            return []

    async def _parse_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse transaction to extract swap details

        Returns:
            Dict with swap info if it's a token swap, None otherwise
        """
        try:
            sig = Signature.from_string(signature)
            tx_response = await self.client.get_transaction(
                sig,
                encoding='jsonParsed',
                max_supported_transaction_version=0
            )

            if not tx_response.value:
                return None

            tx = tx_response.value.transaction

            # Look for Jupiter/swap instructions
            # This is simplified - full implementation would parse all swap types
            swap_info = self._extract_swap_from_transaction(tx)

            if swap_info:
                return {
                    'signature': signature,
                    'timestamp': tx_response.value.block_time,
                    'action': swap_info['action'],  # 'buy' or 'sell'
                    'token_address': swap_info['token'],
                    'amount_sol': swap_info['sol_amount'],
                    'token_amount': swap_info['token_amount'],
                    'price': swap_info['price']
                }

            return None

        except Exception as e:
            logger.debug(f"Error parsing transaction {signature}: {e}")
            return None

    def _extract_swap_from_transaction(self, transaction) -> Optional[Dict]:
        """
        Extract swap details from a parsed Solana transaction.

        Strategy:
        1. Identify which DEX program was used via account keys.
        2. Diff preTokenBalances vs postTokenBalances to find the
           token that was bought (balance increased) or sold (decreased).
        3. Diff preBalances vs postBalances (index 0 = fee-payer) for SOL delta.
        4. Return standardised swap dict.
        """
        try:
            meta = transaction.meta
            if meta is None or (hasattr(meta, 'err') and meta.err is not None):
                return None

            # ---- 1. Identify DEX ----------------------------------------
            # Account keys come back differently depending on encoding.
            # Try both object attribute and dict access.
            account_keys = []
            try:
                msg = transaction.transaction.message
                account_keys = [str(k) for k in msg.account_keys]
            except Exception:
                pass

            dex_name = "unknown"
            for key in account_keys:
                if key in DEX_PROGRAM_IDS:
                    dex_name = DEX_PROGRAM_IDS[key]
                    break

            # Only process known DEX transactions
            if dex_name == "unknown":
                return None

            # ---- 2. Find traded token from balance diffs ----------------
            pre_balances = list(getattr(meta, 'pre_token_balances', None) or [])
            post_balances = list(getattr(meta, 'post_token_balances', None) or [])

            # Build maps: account_index -> {mint, amount}
            pre_map: Dict[int, Dict] = {}
            for b in pre_balances:
                idx = getattr(b, 'account_index', None)
                mint = getattr(b, 'mint', None) or ""
                amount_str = ""
                try:
                    amount_str = b.ui_token_amount.ui_amount_string
                except Exception:
                    pass
                if idx is not None and mint and mint not in (WSOL_MINT, USDC_MINT):
                    pre_map[idx] = {"mint": str(mint), "amount": float(amount_str or 0)}

            post_map: Dict[int, Dict] = {}
            for b in post_balances:
                idx = getattr(b, 'account_index', None)
                mint = getattr(b, 'mint', None) or ""
                amount_str = ""
                try:
                    amount_str = b.ui_token_amount.ui_amount_string
                except Exception:
                    pass
                if idx is not None and mint and mint not in (WSOL_MINT, USDC_MINT):
                    post_map[idx] = {"mint": str(mint), "amount": float(amount_str or 0)}

            # Find the token whose balance changed most
            bought_token = None
            sold_token = None
            max_increase = 0.0
            max_decrease = 0.0

            all_indices = set(pre_map) | set(post_map)
            for idx in all_indices:
                pre_amt = pre_map.get(idx, {}).get("amount", 0.0)
                post_amt = post_map.get(idx, {}).get("amount", 0.0)
                mint = (post_map.get(idx) or pre_map.get(idx, {})).get("mint", "")
                if not mint:
                    continue
                delta = post_amt - pre_amt
                if delta > max_increase:
                    max_increase = delta
                    bought_token = mint
                elif delta < -max_decrease:
                    max_decrease = abs(delta)
                    sold_token = mint

            # Determine action and token address
            if bought_token:
                action = "buy"
                token_address = bought_token
            elif sold_token:
                action = "sell"
                token_address = sold_token
            else:
                return None

            # ---- 3. SOL delta for value estimate -----------------------
            sol_value_usd = 0.0
            try:
                pre_sol = list(getattr(meta, 'pre_balances', []) or [])
                post_sol = list(getattr(meta, 'post_balances', []) or [])
                if pre_sol and post_sol:
                    # Index 0 is fee-payer / main wallet
                    sol_delta_lamports = abs(post_sol[0] - pre_sol[0])
                    sol_delta = sol_delta_lamports / 1_000_000_000
                    # Quick price estimate (replaced by live price in caller)
                    sol_value_usd = sol_delta * 150.0
            except Exception:
                pass

            return {
                "token": token_address,
                "action": action,
                "sol_amount": sol_value_usd / 150.0,
                "token_amount": max_increase if action == "buy" else max_decrease,
                "price": 0.0,  # Caller can enrich with live price
                "value_usd": sol_value_usd,
                "dex": dex_name,
            }

        except Exception as exc:
            logger.debug(f"_extract_swap_from_transaction error: {exc}")
            return None

    async def monitor_wallets(self, callback=None) -> List[Dict]:
        """
        Monitor all tracked wallets for new transactions

        Args:
            callback: Optional function to call when new trade detected

        Returns:
            List of new trades from all wallets
        """
        new_trades = []

        for wallet_address, wallet_info in self.tracked_wallets.items():
            try:
                # Get recent transactions
                transactions = await self.get_recent_transactions(wallet_address, limit=50)

                for tx in transactions:
                    # Update stats
                    wallet_info['total_trades'] += 1

                    # Store in history
                    if wallet_address not in self.transaction_history:
                        self.transaction_history[wallet_address] = []
                    self.transaction_history[wallet_address].append(tx)

                    # Callback for new trade
                    if callback:
                        await callback(wallet_address, wallet_info, tx)

                    new_trades.append({
                        'wallet': wallet_address,
                        'nickname': wallet_info['nickname'],
                        'auto_copy': wallet_info['auto_copy'],
                        'copy_percentage': wallet_info['copy_percentage'],
                        **tx
                    })

                    logger.info(
                        f"New trade from {wallet_info['nickname']}: "
                        f"{tx['action'].upper()} {tx.get('token_address', 'unknown')[:8]}"
                    )

            except Exception as e:
                logger.error(f"Error monitoring {wallet_address[:8]}: {e}")

        return new_trades

    async def get_wallet_stats(self, wallet_address: str) -> Dict:
        """Get performance stats for tracked wallet"""
        if wallet_address not in self.tracked_wallets:
            return {}

        wallet_info = self.tracked_wallets[wallet_address]
        history = self.transaction_history.get(wallet_address, [])

        # Calculate P&L from history
        total_profit = 0.0
        successful_trades = 0

        # Simplified P&L calculation
        # Full version would match buys/sells and calculate realized profit
        for tx in history:
            # Placeholder logic
            pass

        return {
            'address': wallet_address,
            'nickname': wallet_info['nickname'],
            'total_trades': wallet_info['total_trades'],
            'successful_trades': successful_trades,
            'success_rate': successful_trades / wallet_info['total_trades'] if wallet_info['total_trades'] > 0 else 0,
            'total_profit': total_profit,
            'tracking_duration': (datetime.now() - wallet_info['added_at']).total_seconds() / 3600,
            'recent_trades': len(history[-20:])  # Last 20 trades
        }

    def get_all_tracked_wallets(self) -> List[Dict]:
        """Get list of all tracked wallets with stats"""
        result = []
        for wallet_address in self.tracked_wallets:
            stats = asyncio.run(self.get_wallet_stats(wallet_address))
            result.append(stats)
        return result

    async def find_profitable_wallets(
        self,
        min_trades: int = 10,
        min_success_rate: float = 0.6,
        min_profit_sol: float = 5.0
    ) -> List[str]:
        """
        Search for profitable wallets on-chain

        This is advanced feature - would require:
        1. Monitoring DEX transactions
        2. Identifying wallet addresses
        3. Calculating their P&L
        4. Ranking by profitability

        Returns:
            List of wallet addresses that meet criteria
        """
        # Placeholder - actual implementation would:
        # - Query recent DEX transactions
        # - Group by wallet
        # - Calculate P&L per wallet
        # - Filter by criteria
        # - Return top performers

        logger.info("Searching for profitable wallets...")
        logger.warning("Auto-discovery not yet implemented - add wallets manually")
        return []

    async def analyze_wallet_pattern(self, wallet_address: str) -> Dict:
        """
        Analyze trading patterns of a wallet

        Returns:
            Dict with pattern analysis
        """
        history = self.transaction_history.get(wallet_address, [])

        if not history:
            return {'error': 'No transaction history'}

        # Pattern analysis
        buy_count = sum(1 for tx in history if tx['action'] == 'buy')
        sell_count = sum(1 for tx in history if tx['action'] == 'sell')

        avg_hold_time = 0  # Would calculate from matched buy/sell pairs
        favorite_tokens = {}  # Count token appearances

        for tx in history:
            token = tx.get('token_address', 'unknown')
            favorite_tokens[token] = favorite_tokens.get(token, 0) + 1

        # Find most traded token
        top_token = max(favorite_tokens.items(), key=lambda x: x[1]) if favorite_tokens else (None, 0)

        return {
            'total_transactions': len(history),
            'buy_count': buy_count,
            'sell_count': sell_count,
            'avg_hold_time_hours': avg_hold_time,
            'most_traded_token': top_token[0] if top_token[0] else None,
            'most_traded_token_count': top_token[1] if top_token[0] else 0,
            'unique_tokens': len(favorite_tokens)
        }

    async def close(self):
        """Close RPC client"""
        await self.client.close()


class SmartMoneyTracker:
    """
    Track known "smart money" wallets from various sources
    """

    # Known smart money wallet addresses (examples - replace with real ones)
    KNOWN_SMART_WALLETS = {
        # These would be addresses of successful traders
        # Found through:
        # - GMGN.ai smart money tracking
        # - Dexscreener wallet analysis
        # - Community-known successful wallets
    }

    def __init__(self, rpc_url: str):
        self.wallet_tracker = WalletTracker(rpc_url)

    def load_smart_money_wallets(self):
        """Load known smart money wallets into tracker"""
        for address, info in self.KNOWN_SMART_WALLETS.items():
            self.wallet_tracker.add_wallet(
                address,
                nickname=info.get('nickname'),
                auto_copy=info.get('auto_copy', True),
                copy_percentage=info.get('copy_percentage', 0.5)  # 50% of their size
            )

    async def sync_from_gmgn(self):
        """
        Sync smart money wallets from GMGN.ai

        Would query GMGN API for current smart money list
        """
        # Placeholder for GMGN integration
        logger.info("GMGN smart money sync not yet implemented")
        pass

    async def monitor_and_copy(self, trader_callback):
        """
        Monitor smart money wallets and trigger copy trades

        Args:
            trader_callback: Function to call when trade should be copied
                           callback(wallet_info, trade_details)
        """
        while True:
            try:
                new_trades = await self.wallet_tracker.monitor_wallets()

                for trade in new_trades:
                    if trade['auto_copy']:
                        # Calculate position size based on copy percentage
                        copy_sol_amount = trade['amount_sol'] * trade['copy_percentage']

                        # Trigger callback to execute copy trade
                        await trader_callback({
                            'action': trade['action'],
                            'token_address': trade['token_address'],
                            'amount_sol': copy_sol_amount,
                            'source_wallet': trade['wallet'],
                            'source_nickname': trade['nickname'],
                            'reason': f"Copy trade from {trade['nickname']}"
                        })

                # Poll every 10 seconds
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in smart money monitor loop: {e}")
                await asyncio.sleep(30)

    async def close(self):
        """Cleanup"""
        await self.wallet_tracker.close()
