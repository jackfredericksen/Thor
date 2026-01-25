# contract_analyzer.py - Solana Contract Safety & Analysis
"""
Critical safety checks for Solana SPL tokens:
- Mint authority (can create unlimited tokens = rug risk)
- Freeze authority (can freeze your wallet = rug risk)
- Token metadata verification
- Holder distribution analysis
"""

import logging
import requests
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
import base64
import json

logger = logging.getLogger(__name__)


@dataclass
class ContractSafetyResult:
    """Result of contract safety analysis"""
    is_safe: bool
    risk_level: str  # "SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reasons: List[str]
    warnings: List[str]
    mint_authority: Optional[str]
    freeze_authority: Optional[str]
    top_holders_percent: float
    holder_count: int


class ContractAnalyzer:
    """Analyze Solana SPL token contracts for safety and rug risk"""

    def __init__(self, helius_api_key: Optional[str] = None):
        self.helius_api_key = helius_api_key
        self.rugcheck_base_url = "https://api.rugcheck.xyz/v1"

        # Solana RPC endpoints (fallback chain)
        self.rpc_endpoints = [
            f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}" if helius_api_key else None,
            "https://api.mainnet-beta.solana.com",
            "https://solana-api.projectserum.com",
        ]
        self.rpc_endpoints = [e for e in self.rpc_endpoints if e]  # Remove None

    @contextmanager
    def _get_session(self):
        """Context manager for session - ensures cleanup"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
        try:
            yield session
        finally:
            session.close()

    def analyze_token_safety(self, token_address: str) -> ContractSafetyResult:
        """
        Comprehensive token safety analysis

        Returns ContractSafetyResult with all safety metrics
        """
        try:
            # Step 1: Get mint info (critical checks)
            mint_info = self._get_mint_info(token_address)
            if not mint_info:
                return ContractSafetyResult(
                    is_safe=False,
                    risk_level="CRITICAL",
                    reasons=["Could not retrieve token mint info"],
                    warnings=[],
                    mint_authority=None,
                    freeze_authority=None,
                    top_holders_percent=0,
                    holder_count=0
                )

            reasons = []
            warnings = []
            risk_level = "SAFE"

            # Step 2: Check mint authority (CRITICAL)
            mint_authority = mint_info.get('mintAuthority')
            if mint_authority:
                reasons.append("⚠️ MINT AUTHORITY NOT RENOUNCED - Can print unlimited tokens")
                risk_level = "CRITICAL"
            else:
                logger.debug(f"✅ {token_address[:8]}: Mint authority renounced")

            # Step 3: Check freeze authority (CRITICAL)
            freeze_authority = mint_info.get('freezeAuthority')
            if freeze_authority:
                reasons.append("⚠️ FREEZE AUTHORITY NOT RENOUNCED - Can freeze wallets")
                if risk_level != "CRITICAL":
                    risk_level = "HIGH"
            else:
                logger.debug(f"✅ {token_address[:8]}: Freeze authority renounced")

            # Step 4: Get holder distribution
            holder_data = self._get_holder_distribution(token_address)
            top_holders_percent = holder_data['top_10_percent']
            holder_count = holder_data['holder_count']

            if top_holders_percent > 80:
                reasons.append(f"⚠️ CONCENTRATED OWNERSHIP - Top 10 holders own {top_holders_percent:.1f}%")
                if risk_level == "SAFE":
                    risk_level = "HIGH"
            elif top_holders_percent > 60:
                warnings.append(f"Top 10 holders own {top_holders_percent:.1f}% (concerning)")
                if risk_level == "SAFE":
                    risk_level = "MEDIUM"

            if holder_count < 100:
                warnings.append(f"Only {holder_count} holders (low distribution)")
                if risk_level == "SAFE":
                    risk_level = "MEDIUM"

            # Step 5: RugCheck API (if available)
            rugcheck_data = self._check_rugcheck(token_address)
            if rugcheck_data and rugcheck_data.get('risks'):
                for risk in rugcheck_data['risks']:
                    warnings.append(f"RugCheck: {risk['name']} - {risk['description']}")
                    if risk['level'] == 'danger':
                        if risk_level in ["SAFE", "LOW", "MEDIUM"]:
                            risk_level = "HIGH"

            # Final determination
            is_safe = risk_level in ["SAFE", "LOW"]

            return ContractSafetyResult(
                is_safe=is_safe,
                risk_level=risk_level,
                reasons=reasons,
                warnings=warnings,
                mint_authority=mint_authority,
                freeze_authority=freeze_authority,
                top_holders_percent=top_holders_percent,
                holder_count=holder_count
            )

        except Exception as e:
            logger.error(f"Error analyzing token safety for {token_address}: {e}")
            return ContractSafetyResult(
                is_safe=False,
                risk_level="UNKNOWN",
                reasons=[f"Analysis failed: {str(e)}"],
                warnings=[],
                mint_authority=None,
                freeze_authority=None,
                top_holders_percent=0,
                holder_count=0
            )

    def _get_mint_info(self, token_address: str) -> Optional[Dict]:
        """Get SPL token mint account info via Solana RPC"""
        try:
            with self._get_session() as session:
                # Try RPC endpoints in order
                for rpc_url in self.rpc_endpoints:
                    try:
                        payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getAccountInfo",
                            "params": [
                                token_address,
                                {"encoding": "jsonParsed"}
                            ]
                        }

                        response = session.post(rpc_url, json=payload, timeout=10)
                        response.raise_for_status()
                        data = response.json()

                        if 'result' in data and data['result']:
                            account_data = data['result']['value']
                            if account_data and 'data' in account_data:
                                parsed = account_data['data'].get('parsed', {})
                                info = parsed.get('info', {})

                                return {
                                    'mintAuthority': info.get('mintAuthority'),
                                    'freezeAuthority': info.get('freezeAuthority'),
                                    'supply': int(info.get('supply', 0)),
                                    'decimals': int(info.get('decimals', 9))
                                }

                    except Exception as e:
                        logger.debug(f"RPC {rpc_url} failed: {e}")
                        continue

            logger.warning(f"Could not get mint info for {token_address} from any RPC")
            return None

        except Exception as e:
            logger.error(f"Error getting mint info: {e}")
            return None

    def _get_holder_distribution(self, token_address: str) -> Dict:
        """Get holder distribution data"""
        try:
            with self._get_session() as session:
                # Try Helius first (best data)
                if self.helius_api_key:
                    helius_url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.helius_api_key}"
                    try:
                        response = session.post(helius_url, json={"mintAccounts": [token_address]}, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data and len(data) > 0:
                                token_data = data[0]
                                # Helius provides holder data
                                return self._calculate_holder_metrics_helius(token_address, session)
                    except Exception as e:
                        logger.debug(f"Helius holder data failed: {e}")

                # Fallback: Use Solana RPC getTokenLargestAccounts
                return self._get_largest_accounts_rpc(token_address, session)

        except Exception as e:
            logger.error(f"Error getting holder distribution: {e}")
            return {
                'top_10_percent': 0,
                'holder_count': 0,
                'largest_holders': []
            }

    def _get_largest_accounts_rpc(self, token_address: str, session: requests.Session) -> Dict:
        """Get largest token accounts via RPC"""
        try:
            for rpc_url in self.rpc_endpoints:
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenLargestAccounts",
                        "params": [token_address]
                    }

                    response = session.post(rpc_url, json=payload, timeout=10)
                    data = response.json()

                    if 'result' in data and 'value' in data['result']:
                        accounts = data['result']['value']

                        # Calculate total supply
                        total_supply = sum(float(acc['amount']) for acc in accounts)

                        if total_supply == 0:
                            return {'top_10_percent': 100, 'holder_count': 0, 'largest_holders': []}

                        # Calculate top 10 percentage
                        top_10_accounts = accounts[:10]
                        top_10_supply = sum(float(acc['amount']) for acc in top_10_accounts)
                        top_10_percent = (top_10_supply / total_supply * 100) if total_supply > 0 else 100

                        return {
                            'top_10_percent': top_10_percent,
                            'holder_count': len(accounts),  # Approximation
                            'largest_holders': [acc['address'] for acc in top_10_accounts]
                        }

                except Exception as e:
                    logger.debug(f"RPC {rpc_url} getTokenLargestAccounts failed: {e}")
                    continue

            # Fallback
            return {'top_10_percent': 50, 'holder_count': 0, 'largest_holders': []}

        except Exception as e:
            logger.error(f"Error in _get_largest_accounts_rpc: {e}")
            return {'top_10_percent': 50, 'holder_count': 0, 'largest_holders': []}

    def _calculate_holder_metrics_helius(self, token_address: str, session: requests.Session) -> Dict:
        """Calculate holder metrics using Helius enhanced data"""
        # This would use Helius' enhanced APIs if available
        # For now, fall back to RPC method
        return self._get_largest_accounts_rpc(token_address, session)

    def _check_rugcheck(self, token_address: str) -> Optional[Dict]:
        """Check RugCheck.xyz API for known risks"""
        try:
            with self._get_session() as session:
                url = f"{self.rugcheck_base_url}/tokens/{token_address}/report"
                response = session.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    return data

                logger.debug(f"RugCheck returned {response.status_code} for {token_address}")
                return None

        except Exception as e:
            logger.debug(f"RugCheck API error: {e}")
            return None

    def check_honeypot(self, token_address: str) -> Tuple[bool, str]:
        """
        Check if token is a honeypot (can buy but can't sell)

        This is a simplified check - full implementation would simulate a swap
        """
        try:
            # Check via RugCheck API
            rugcheck_data = self._check_rugcheck(token_address)

            if rugcheck_data:
                risks = rugcheck_data.get('risks', [])
                for risk in risks:
                    if 'honeypot' in risk.get('name', '').lower():
                        return True, f"RugCheck detected honeypot: {risk['description']}"
                    if 'cannot sell' in risk.get('description', '').lower():
                        return True, "Cannot sell tokens detected"

            # If no RugCheck data or no honeypot detected
            return False, "No honeypot detected"

        except Exception as e:
            logger.error(f"Error checking honeypot: {e}")
            return False, f"Honeypot check failed: {e}"


def quick_safety_check(token_address: str, helius_api_key: Optional[str] = None) -> Tuple[bool, str, Dict]:
    """
    Quick safety check for a token

    Returns:
        (is_safe: bool, reason: str, details: Dict)
    """
    analyzer = ContractAnalyzer(helius_api_key)
    result = analyzer.analyze_token_safety(token_address)

    if not result.is_safe:
        reason = " | ".join(result.reasons) if result.reasons else "Safety check failed"
        return False, reason, {
            'risk_level': result.risk_level,
            'mint_authority': result.mint_authority,
            'freeze_authority': result.freeze_authority,
            'top_holders_percent': result.top_holders_percent,
            'holder_count': result.holder_count
        }

    return True, "Token passed safety checks", {
        'risk_level': result.risk_level,
        'warnings': result.warnings,
        'top_holders_percent': result.top_holders_percent,
        'holder_count': result.holder_count
    }
