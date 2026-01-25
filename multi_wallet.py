"""
Multi-Wallet Manager
Manage multiple trading wallets for diversification and anonymity
"""

import logging
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import base58
from solders.keypair import Keypair
from api_clients.solana_trader import SolanaTrader

logger = logging.getLogger(__name__)


@dataclass
class WalletInfo:
    """Information about a managed wallet"""
    wallet_id: str
    address: str
    nickname: str
    trader_client: SolanaTrader
    enabled: bool = True
    total_trades: int = 0
    total_profit_sol: float = 0.0
    sol_balance: float = 0.0
    created_at: datetime = None
    last_used_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class MultiWalletManager:
    """Manage multiple trading wallets"""

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.wallets: Dict[str, WalletInfo] = {}
        self.current_wallet_id: Optional[str] = None
        self.rotation_strategy = 'round_robin'  # round_robin, random, balance_based

    def add_wallet(
        self,
        private_key: str,
        nickname: str,
        wallet_id: Optional[str] = None,
        set_as_current: bool = False
    ) -> str:
        """
        Add wallet to manager

        Args:
            private_key: Base58 encoded private key
            nickname: Friendly name for wallet
            wallet_id: Optional custom ID
            set_as_current: Whether to set as active wallet

        Returns:
            Wallet ID
        """
        try:
            # Create trader client for this wallet
            trader = SolanaTrader(private_key, self.rpc_url)

            if wallet_id is None:
                wallet_id = f"wallet_{len(self.wallets) + 1}"

            wallet_info = WalletInfo(
                wallet_id=wallet_id,
                address=trader.wallet_address,
                nickname=nickname,
                trader_client=trader
            )

            self.wallets[wallet_id] = wallet_info

            logger.info(
                f"Wallet added: {nickname} ({wallet_info.address[:8]}...)"
            )

            if set_as_current or len(self.wallets) == 1:
                self.current_wallet_id = wallet_id

            return wallet_id

        except Exception as e:
            logger.error(f"Failed to add wallet: {e}")
            raise

    def generate_new_wallet(
        self,
        nickname: str,
        fund_amount_sol: Optional[float] = None
    ) -> str:
        """
        Generate new random wallet

        Args:
            nickname: Friendly name
            fund_amount_sol: Optional - auto-fund from main wallet

        Returns:
            Wallet ID
        """
        try:
            # Generate new keypair
            new_keypair = Keypair()
            private_key_b58 = base58.b58encode(bytes(new_keypair)).decode('utf-8')

            # Add to manager
            wallet_id = self.add_wallet(private_key_b58, nickname)

            logger.info(f"Generated new wallet: {nickname}")

            # Auto-fund if requested
            if fund_amount_sol and self.current_wallet_id:
                asyncio.create_task(
                    self._transfer_sol(
                        self.current_wallet_id,
                        wallet_id,
                        fund_amount_sol
                    )
                )

            return wallet_id

        except Exception as e:
            logger.error(f"Failed to generate wallet: {e}")
            raise

    def remove_wallet(self, wallet_id: str) -> bool:
        """Remove wallet from manager"""
        if wallet_id not in self.wallets:
            return False

        wallet = self.wallets[wallet_id]
        logger.info(f"Removing wallet: {wallet.nickname}")

        # Don't allow removing if it's the only wallet
        if len(self.wallets) == 1:
            logger.error("Cannot remove last wallet")
            return False

        # Switch current wallet if removing active one
        if wallet_id == self.current_wallet_id:
            remaining = [wid for wid in self.wallets.keys() if wid != wallet_id]
            self.current_wallet_id = remaining[0]

        del self.wallets[wallet_id]
        return True

    def get_current_wallet(self) -> Optional[WalletInfo]:
        """Get currently active wallet"""
        if self.current_wallet_id:
            return self.wallets.get(self.current_wallet_id)
        return None

    def get_current_trader(self) -> Optional[SolanaTrader]:
        """Get trader client for current wallet"""
        wallet = self.get_current_wallet()
        return wallet.trader_client if wallet else None

    def rotate_wallet(self) -> Optional[WalletInfo]:
        """
        Rotate to next wallet based on strategy

        Returns:
            New current wallet
        """
        if not self.wallets:
            return None

        if self.rotation_strategy == 'round_robin':
            return self._rotate_round_robin()
        elif self.rotation_strategy == 'random':
            return self._rotate_random()
        elif self.rotation_strategy == 'balance_based':
            return self._rotate_balance_based()
        else:
            return self._rotate_round_robin()

    def _rotate_round_robin(self) -> Optional[WalletInfo]:
        """Rotate to next wallet in sequence"""
        wallet_ids = list(self.wallets.keys())

        if not wallet_ids:
            return None

        # Find current index
        try:
            current_idx = wallet_ids.index(self.current_wallet_id)
            next_idx = (current_idx + 1) % len(wallet_ids)
        except (ValueError, TypeError):
            next_idx = 0

        self.current_wallet_id = wallet_ids[next_idx]
        wallet = self.wallets[self.current_wallet_id]

        logger.info(f"Rotated to wallet: {wallet.nickname}")
        return wallet

    def _rotate_random(self) -> Optional[WalletInfo]:
        """Rotate to random wallet"""
        import random

        enabled_wallets = [
            wid for wid, w in self.wallets.items()
            if w.enabled and wid != self.current_wallet_id
        ]

        if not enabled_wallets:
            return self.get_current_wallet()

        self.current_wallet_id = random.choice(enabled_wallets)
        wallet = self.wallets[self.current_wallet_id]

        logger.info(f"Randomly rotated to: {wallet.nickname}")
        return wallet

    def _rotate_balance_based(self) -> Optional[WalletInfo]:
        """Rotate to wallet with highest balance"""
        enabled_wallets = {
            wid: w for wid, w in self.wallets.items()
            if w.enabled
        }

        if not enabled_wallets:
            return None

        # Find wallet with highest balance
        best_wallet_id = max(
            enabled_wallets.keys(),
            key=lambda wid: enabled_wallets[wid].sol_balance
        )

        self.current_wallet_id = best_wallet_id
        wallet = self.wallets[best_wallet_id]

        logger.info(f"Rotated to highest balance: {wallet.nickname} ({wallet.sol_balance} SOL)")
        return wallet

    async def update_all_balances(self):
        """Update SOL balance for all wallets"""
        tasks = []

        for wallet_id, wallet in self.wallets.items():
            tasks.append(self._update_wallet_balance(wallet_id))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_wallet_balance(self, wallet_id: str):
        """Update balance for specific wallet"""
        try:
            wallet = self.wallets[wallet_id]
            balance = await wallet.trader_client.get_sol_balance()
            wallet.sol_balance = balance

            logger.debug(f"{wallet.nickname}: {balance:.4f} SOL")

        except Exception as e:
            logger.error(f"Error updating balance for {wallet_id}: {e}")

    async def _transfer_sol(
        self,
        from_wallet_id: str,
        to_wallet_id: str,
        amount_sol: float
    ) -> bool:
        """Transfer SOL between managed wallets"""
        try:
            from_wallet = self.wallets.get(from_wallet_id)
            to_wallet = self.wallets.get(to_wallet_id)

            if not from_wallet or not to_wallet:
                logger.error("Invalid wallet IDs for transfer")
                return False

            logger.info(
                f"Transferring {amount_sol} SOL from {from_wallet.nickname} "
                f"to {to_wallet.nickname}"
            )

            # This would use Solana transfer instruction
            # Placeholder for actual implementation
            logger.warning("SOL transfer not yet implemented")

            return False

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return False

    def get_all_wallets(self) -> List[Dict]:
        """Get info for all wallets"""
        return [
            {
                'wallet_id': wallet.wallet_id,
                'address': wallet.address,
                'nickname': wallet.nickname,
                'enabled': wallet.enabled,
                'sol_balance': wallet.sol_balance,
                'total_trades': wallet.total_trades,
                'total_profit_sol': wallet.total_profit_sol,
                'is_current': wallet.wallet_id == self.current_wallet_id,
                'last_used': wallet.last_used_at.isoformat() if wallet.last_used_at else None
            }
            for wallet in self.wallets.values()
        ]

    def get_total_portfolio_value(self) -> float:
        """Get combined SOL balance across all wallets"""
        return sum(w.sol_balance for w in self.wallets.values())

    def enable_wallet(self, wallet_id: str):
        """Enable wallet for rotation"""
        if wallet_id in self.wallets:
            self.wallets[wallet_id].enabled = True
            logger.info(f"Enabled wallet: {self.wallets[wallet_id].nickname}")

    def disable_wallet(self, wallet_id: str):
        """Disable wallet from rotation"""
        if wallet_id in self.wallets:
            self.wallets[wallet_id].enabled = False
            logger.info(f"Disabled wallet: {self.wallets[wallet_id].nickname}")

            # Switch if disabling current
            if wallet_id == self.current_wallet_id:
                self.rotate_wallet()

    def set_rotation_strategy(self, strategy: str):
        """
        Set wallet rotation strategy

        Args:
            strategy: 'round_robin', 'random', or 'balance_based'
        """
        valid_strategies = ['round_robin', 'random', 'balance_based']

        if strategy not in valid_strategies:
            logger.error(f"Invalid strategy. Choose from: {valid_strategies}")
            return

        self.rotation_strategy = strategy
        logger.info(f"Rotation strategy set to: {strategy}")

    async def execute_trade_with_rotation(
        self,
        token_address: str,
        amount_sol: float,
        action: str = 'buy'
    ) -> Optional[str]:
        """
        Execute trade and automatically rotate to next wallet

        Args:
            token_address: Token to trade
            amount_sol: Amount in SOL
            action: 'buy' or 'sell'

        Returns:
            Transaction signature
        """
        current_wallet = self.get_current_wallet()

        if not current_wallet:
            logger.error("No wallet available")
            return None

        try:
            # Execute trade
            logger.info(
                f"Executing {action} with {current_wallet.nickname}: "
                f"{amount_sol} SOL of {token_address[:8]}"
            )

            if action == 'buy':
                result = await current_wallet.trader_client.swap_sol_for_token(
                    token_address, amount_sol
                )
            else:
                result = await current_wallet.trader_client.swap_token_for_sol(
                    token_address, amount_sol
                )

            if result:
                # Update wallet stats
                current_wallet.total_trades += 1
                current_wallet.last_used_at = datetime.now()

                # Rotate to next wallet
                self.rotate_wallet()

                return result

            return None

        except Exception as e:
            logger.error(f"Trade failed: {e}")
            return None

    def get_wallet_stats(self, wallet_id: str) -> Optional[Dict]:
        """Get detailed stats for wallet"""
        if wallet_id not in self.wallets:
            return None

        wallet = self.wallets[wallet_id]

        return {
            'wallet_id': wallet.wallet_id,
            'address': wallet.address,
            'nickname': wallet.nickname,
            'sol_balance': wallet.sol_balance,
            'total_trades': wallet.total_trades,
            'total_profit_sol': wallet.total_profit_sol,
            'avg_profit_per_trade': wallet.total_profit_sol / wallet.total_trades if wallet.total_trades > 0 else 0,
            'enabled': wallet.enabled,
            'created_at': wallet.created_at.isoformat(),
            'last_used_at': wallet.last_used_at.isoformat() if wallet.last_used_at else None,
            'days_active': (datetime.now() - wallet.created_at).days
        }


class WalletPoolManager(MultiWalletManager):
    """
    Advanced wallet pool with automatic rebalancing

    Features:
    - Auto-fund new wallets from main wallet
    - Rebalance SOL across wallets
    - Retire low-balance wallets
    - Generate fresh wallets on schedule
    """

    def __init__(self, rpc_url: str, main_wallet_id: str = None):
        super().__init__(rpc_url)
        self.main_wallet_id = main_wallet_id
        self.target_wallet_balance = 0.5  # SOL per wallet
        self.min_wallet_balance = 0.1  # Retire below this

    async def auto_rebalance(self):
        """Rebalance SOL across all wallets"""
        logger.info("Starting wallet pool rebalancing...")

        await self.update_all_balances()

        # Calculate target distribution
        total_sol = self.get_total_portfolio_value()
        num_wallets = len(self.wallets)

        target_per_wallet = total_sol / num_wallets if num_wallets > 0 else 0

        logger.info(
            f"Rebalancing {total_sol:.2f} SOL across {num_wallets} wallets "
            f"(target: {target_per_wallet:.2f} SOL each)"
        )

        # Identify wallets needing funds and wallets with excess
        needs_funds = []
        has_excess = []

        for wallet_id, wallet in self.wallets.items():
            if wallet.sol_balance < target_per_wallet * 0.8:  # Below 80% of target
                needs_funds.append((wallet_id, target_per_wallet - wallet.sol_balance))
            elif wallet.sol_balance > target_per_wallet * 1.2:  # Above 120% of target
                has_excess.append((wallet_id, wallet.sol_balance - target_per_wallet))

        # Execute transfers
        for from_id, excess_amount in has_excess:
            for to_id, needed_amount in needs_funds:
                transfer_amount = min(excess_amount, needed_amount)

                if transfer_amount > 0.01:  # Minimum 0.01 SOL
                    await self._transfer_sol(from_id, to_id, transfer_amount)

                    excess_amount -= transfer_amount
                    if excess_amount <= 0:
                        break

        logger.info("Rebalancing complete")

    async def retire_low_balance_wallets(self):
        """Remove wallets with very low balances"""
        to_retire = []

        for wallet_id, wallet in self.wallets.items():
            if wallet.sol_balance < self.min_wallet_balance:
                to_retire.append(wallet_id)

        for wallet_id in to_retire:
            logger.info(f"Retiring low-balance wallet: {wallet_id}")
            self.remove_wallet(wallet_id)

    async def expand_pool(self, num_new_wallets: int = 1):
        """Generate new wallets and fund them"""
        logger.info(f"Expanding pool by {num_new_wallets} wallets")

        for i in range(num_new_wallets):
            nickname = f"auto_wallet_{len(self.wallets) + 1}"
            self.generate_new_wallet(
                nickname=nickname,
                fund_amount_sol=self.target_wallet_balance
            )
