"""
Jito MEV Bundle Client
Enables atomic transaction bundling for faster execution
"""

import logging
import asyncio
import time
from typing import List, Optional
import aiohttp
from solders.transaction import VersionedTransaction
from solders.signature import Signature
import base58

logger = logging.getLogger(__name__)


class JitoClient:
    """Client for Jito MEV bundle submission"""

    # Jito block engine endpoints (rotate for reliability)
    JITO_ENDPOINTS = [
        "https://mainnet.block-engine.jito.wtf",
        "https://amsterdam.mainnet.block-engine.jito.wtf",
        "https://frankfurt.mainnet.block-engine.jito.wtf",
        "https://ny.mainnet.block-engine.jito.wtf",
        "https://tokyo.mainnet.block-engine.jito.wtf",
    ]

    # Jito tip accounts (rotate to distribute load)
    TIP_ACCOUNTS = [
        "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
        "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
        "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
        "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
        "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
        "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
        "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
        "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
    ]

    def __init__(self):
        self.current_endpoint_idx = 0
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def _get_endpoint(self) -> str:
        """Get next Jito endpoint (round-robin)"""
        endpoint = self.JITO_ENDPOINTS[self.current_endpoint_idx]
        self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.JITO_ENDPOINTS)
        return endpoint

    def _get_tip_account(self) -> str:
        """Get random tip account"""
        import random
        return random.choice(self.TIP_ACCOUNTS)

    async def send_bundle(
        self,
        transactions: List[VersionedTransaction],
        tip_lamports: int = 10_000  # 0.00001 SOL tip (minimum)
    ) -> Optional[str]:
        """
        Send bundle of transactions to Jito

        Args:
            transactions: List of signed transactions
            tip_lamports: Tip amount in lamports (higher = better priority)

        Returns:
            Bundle ID if successful, None otherwise
        """
        try:
            # Serialize transactions
            serialized_txs = [
                base58.b58encode(tx.to_bytes()).decode('utf-8')
                for tx in transactions
            ]

            # Prepare bundle
            bundle = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendBundle",
                "params": [serialized_txs]
            }

            # Send to Jito
            endpoint = self._get_endpoint()
            session = await self._get_session()

            async with session.post(
                f"{endpoint}/api/v1/bundles",
                json=bundle,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    bundle_id = result.get('result')
                    logger.info(f"Jito bundle submitted: {bundle_id}")
                    return bundle_id
                else:
                    error = await response.text()
                    logger.error(f"Jito bundle failed: {response.status} - {error}")
                    return None

        except Exception as e:
            logger.error(f"Error sending Jito bundle: {e}")
            return None

    async def get_bundle_status(self, bundle_id: str) -> Optional[Dict]:
        """Check bundle status"""
        try:
            endpoint = self._get_endpoint()
            session = await self._get_session()

            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBundleStatuses",
                "params": [[bundle_id]]
            }

            async with session.post(
                f"{endpoint}/api/v1/bundles",
                json=request
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('result', {})
                return None

        except Exception as e:
            logger.error(f"Error checking bundle status: {e}")
            return None

    async def send_transaction_with_jito(
        self,
        transaction: VersionedTransaction,
        tip_lamports: int = 10_000,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Send single transaction as Jito bundle

        Args:
            transaction: Signed transaction
            tip_lamports: Tip in lamports (recommend 0.006 SOL = 6_000_000 for sniping)
            max_retries: Number of retry attempts

        Returns:
            Transaction signature if successful
        """
        for attempt in range(max_retries):
            try:
                # Create bundle with just this transaction
                bundle_id = await self.send_bundle([transaction], tip_lamports)

                if bundle_id:
                    # Wait for bundle to land
                    for _ in range(30):  # 30 second timeout
                        await asyncio.sleep(1)

                        status = await self.get_bundle_status(bundle_id)
                        if status and status.get('bundle_statuses'):
                            bundle_status = status['bundle_statuses'][0]

                            if bundle_status.get('confirmation_status') == 'confirmed':
                                # Extract signature from transaction
                                signatures = transaction.signatures
                                if signatures:
                                    sig_str = str(signatures[0])
                                    logger.info(f"Jito transaction confirmed: {sig_str}")
                                    return sig_str

                            elif bundle_status.get('err'):
                                logger.error(f"Bundle failed: {bundle_status['err']}")
                                break

                    logger.warning(f"Bundle timeout on attempt {attempt + 1}")

            except Exception as e:
                logger.error(f"Jito send attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry

        return None

    async def send_bundle_with_tip(
        self,
        transactions: List[VersionedTransaction],
        tip_sol: float = 0.001
    ) -> Optional[str]:
        """
        Send bundle with SOL tip for priority

        Args:
            transactions: List of signed transactions
            tip_sol: Tip in SOL (0.001 = 1_000_000 lamports)

        Returns:
            Bundle ID
        """
        tip_lamports = int(tip_sol * 1_000_000_000)
        return await self.send_bundle(transactions, tip_lamports)

    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()

    def __del__(self):
        """Cleanup"""
        try:
            if self.session and not self.session.closed:
                asyncio.create_task(self.session.close())
        except:
            pass


class JitoConfig:
    """Jito configuration settings"""

    # Tip amounts (in SOL)
    MIN_TIP = 0.00001      # 10_000 lamports - minimum
    LOW_TIP = 0.0001       # 100_000 lamports - low priority
    MEDIUM_TIP = 0.001     # 1_000_000 lamports - medium priority
    HIGH_TIP = 0.006       # 6_000_000 lamports - high priority (recommended for sniping)
    AGGRESSIVE_TIP = 0.01  # 10_000_000 lamports - very high priority

    @staticmethod
    def get_tip_for_priority(priority: str) -> float:
        """Get tip amount based on priority level"""
        tips = {
            'min': JitoConfig.MIN_TIP,
            'low': JitoConfig.LOW_TIP,
            'medium': JitoConfig.MEDIUM_TIP,
            'high': JitoConfig.HIGH_TIP,
            'aggressive': JitoConfig.AGGRESSIVE_TIP,
        }
        return tips.get(priority.lower(), JitoConfig.MEDIUM_TIP)
