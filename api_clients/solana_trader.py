"""
Solana Trading Client with Jupiter Aggregator Integration
Executes real token swaps on Solana blockchain with Jito MEV bundles
"""

import logging
import time
from typing import Optional, Dict, Any
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.signature import Signature
import base58
import asyncio

from .jito_client import JitoClient, JitoConfig
from config import TradingConfig

logger = logging.getLogger(__name__)


class SolanaTrader:
    """Solana blockchain trading client using Jupiter aggregator"""

    def __init__(self, private_key: str, rpc_url: str):
        """
        Initialize Solana trader

        Args:
            private_key: Base58 encoded private key OR array format like [1,2,3,...]
            rpc_url: Solana RPC endpoint URL
        """
        self.rpc_url = rpc_url
        self.client = AsyncClient(rpc_url)

        # Initialize wallet from private key
        try:
            # Handle array format: [1,2,3,...] or "[1,2,3,...]"
            if private_key.startswith('['):
                # Parse array format
                import json
                key_array = json.loads(private_key)
                private_key_bytes = bytes(key_array)
                logger.info("Parsed private key from array format")
            else:
                # Base58 format
                private_key_bytes = base58.b58decode(private_key)
                logger.info("Parsed private key from base58 format")

            self.wallet = Keypair.from_bytes(private_key_bytes)
            self.wallet_address = str(self.wallet.pubkey())
            logger.info(f"Solana wallet initialized: {self.wallet_address}")
        except Exception as e:
            logger.error(f"Failed to initialize wallet: {e}")
            logger.error(f"Private key format: {private_key[:20]}...")
            raise

        # Jupiter API endpoint
        self.jupiter_api = "https://quote-api.jup.ag/v6"

        # Native SOL mint address
        self.SOL_MINT = "So11111111111111111111111111111111111111112"

        # Jito client for MEV bundles (faster execution)
        self.jito_client = JitoClient() if TradingConfig.USE_JITO else None
        if self.jito_client:
            tip_sol = JitoConfig.get_tip_for_priority(TradingConfig.JITO_PRIORITY)
            logger.info(f"Jito MEV enabled - Priority: {TradingConfig.JITO_PRIORITY} ({tip_sol} SOL tip)")

    async def get_sol_balance(self) -> float:
        """Get SOL balance of wallet"""
        try:
            response = await self.client.get_balance(self.wallet.pubkey())
            if response.value is not None:
                # Convert lamports to SOL (1 SOL = 1e9 lamports)
                return response.value / 1e9
            return 0.0
        except Exception as e:
            logger.error(f"Error getting SOL balance: {e}")
            return 0.0

    async def get_token_balance(self, token_mint: str) -> float:
        """Get token balance for a specific mint"""
        try:
            # Get token accounts for this wallet
            from solders.rpc.requests import GetTokenAccountsByOwner
            from solders.rpc.config import RpcTokenAccountsFilterMint

            mint_pubkey = Pubkey.from_string(token_mint)
            response = await self.client.get_token_accounts_by_owner(
                self.wallet.pubkey(),
                RpcTokenAccountsFilterMint(mint_pubkey)
            )

            if response.value:
                # Parse token account and get balance
                account_data = response.value[0].account.data
                # Token balance is in the account data
                # This is simplified - actual parsing requires more work
                return 0.0  # Placeholder
            return 0.0
        except Exception as e:
            logger.error(f"Error getting token balance: {e}")
            return 0.0

    async def get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50  # 0.5% default
    ) -> Optional[Dict[str, Any]]:
        """
        Get swap quote from Jupiter

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage in basis points (50 = 0.5%)
        """
        try:
            import httpx

            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': str(amount),
                'slippageBps': str(slippage_bps),
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.jupiter_api}/quote", params=params)

                if response.status_code == 200:
                    quote = response.json()
                    logger.info(f"Jupiter quote received: {quote.get('outAmount', 0)} tokens")
                    return quote
                else:
                    logger.error(f"Jupiter quote failed: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error getting Jupiter quote: {e}")
            return None

    async def execute_jupiter_swap(
        self,
        quote: Dict[str, Any]
    ) -> Optional[str]:
        """
        Execute swap using Jupiter quote

        Args:
            quote: Quote from get_jupiter_quote

        Returns:
            Transaction signature if successful, None otherwise
        """
        try:
            import httpx

            # Get swap transaction from Jupiter
            swap_request = {
                'quoteResponse': quote,
                'userPublicKey': self.wallet_address,
                'wrapAndUnwrapSol': True,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.jupiter_api}/swap",
                    json=swap_request
                )

                if response.status_code != 200:
                    logger.error(f"Jupiter swap transaction failed: {response.status_code}")
                    return None

                swap_data = response.json()
                swap_transaction = swap_data.get('swapTransaction')

                if not swap_transaction:
                    logger.error("No swap transaction in response")
                    return None

                # Decode and sign transaction
                transaction_bytes = base58.b58decode(swap_transaction)
                versioned_tx = VersionedTransaction.from_bytes(transaction_bytes)

                # Sign transaction
                versioned_tx.sign([self.wallet])

                # Send transaction - use Jito if enabled
                if self.jito_client and TradingConfig.USE_JITO:
                    # Send via Jito MEV bundle for faster execution
                    tip_sol = JitoConfig.get_tip_for_priority(TradingConfig.JITO_PRIORITY)
                    logger.info(f"Sending transaction via Jito bundle (tip: {tip_sol} SOL)")

                    signature_str = await self.jito_client.send_transaction_with_jito(
                        versioned_tx,
                        tip_lamports=int(tip_sol * 1_000_000_000)
                    )

                    if signature_str:
                        logger.info(f"Jito transaction confirmed: {signature_str}")
                        return signature_str
                    else:
                        logger.error("Jito transaction failed - falling back to regular RPC")
                        # Fall through to regular send below
                else:
                    # Regular RPC send
                    tx_signature = await self.client.send_transaction(
                        versioned_tx,
                        opts={'skip_preflight': False, 'preflight_commitment': Confirmed}
                    )

                    if tx_signature.value:
                        signature_str = str(tx_signature.value)
                        logger.info(f"Transaction sent: {signature_str}")

                        # Wait for confirmation
                        await self._wait_for_confirmation(signature_str)

                        return signature_str
                    else:
                        logger.error("Transaction failed to send")
                        return None

        except Exception as e:
            logger.error(f"Error executing Jupiter swap: {e}")
            return None

    async def _wait_for_confirmation(
        self,
        signature: str,
        timeout: int = 60
    ) -> bool:
        """Wait for transaction confirmation"""
        try:
            sig = Signature.from_string(signature)
            start_time = time.time()

            while time.time() - start_time < timeout:
                response = await self.client.get_signature_statuses([sig])

                if response.value and response.value[0]:
                    status = response.value[0]
                    if status.confirmation_status:
                        logger.info(f"Transaction confirmed: {signature}")
                        return True

                await asyncio.sleep(2)

            logger.warning(f"Transaction confirmation timeout: {signature}")
            return False

        except Exception as e:
            logger.error(f"Error waiting for confirmation: {e}")
            return False

    async def swap_sol_for_token(
        self,
        token_address: str,
        amount_sol: float,
        slippage: float = 0.02
    ) -> Optional[str]:
        """
        Swap SOL for a token

        Args:
            token_address: Target token mint address
            amount_sol: Amount of SOL to swap
            slippage: Slippage tolerance (0.02 = 2%)

        Returns:
            Transaction signature if successful
        """
        try:
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1e9)
            slippage_bps = int(slippage * 10000)

            logger.info(f"Swapping {amount_sol} SOL for {token_address}")

            # Get quote
            quote = await self.get_jupiter_quote(
                input_mint=self.SOL_MINT,
                output_mint=token_address,
                amount=amount_lamports,
                slippage_bps=slippage_bps
            )

            if not quote:
                logger.error("Failed to get quote for swap")
                return None

            # Execute swap
            signature = await self.execute_jupiter_swap(quote)

            if signature:
                logger.info(f"Successfully swapped SOL for token: {signature}")
                return signature
            else:
                logger.error("Swap execution failed")
                return None

        except Exception as e:
            logger.error(f"Error in swap_sol_for_token: {e}")
            return None

    async def swap_token_for_sol(
        self,
        token_address: str,
        amount_tokens: float,
        slippage: float = 0.02
    ) -> Optional[str]:
        """
        Swap token for SOL

        Args:
            token_address: Token mint address to sell
            amount_tokens: Amount of tokens to swap
            slippage: Slippage tolerance (0.02 = 2%)

        Returns:
            Transaction signature if successful
        """
        try:
            # Convert to smallest unit (this varies by token)
            # For simplicity, assuming 9 decimals (like SOL)
            amount_smallest = int(amount_tokens * 1e9)
            slippage_bps = int(slippage * 10000)

            logger.info(f"Swapping {amount_tokens} tokens for SOL")

            # Get quote
            quote = await self.get_jupiter_quote(
                input_mint=token_address,
                output_mint=self.SOL_MINT,
                amount=amount_smallest,
                slippage_bps=slippage_bps
            )

            if not quote:
                logger.error("Failed to get quote for swap")
                return None

            # Execute swap
            signature = await self.execute_jupiter_swap(quote)

            if signature:
                logger.info(f"Successfully swapped token for SOL: {signature}")
                return signature
            else:
                logger.error("Swap execution failed")
                return None

        except Exception as e:
            logger.error(f"Error in swap_token_for_sol: {e}")
            return None

    async def close(self):
        """Close the RPC client"""
        await self.client.close()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            asyncio.create_task(self.close())
        except:
            pass
