# api_clients/gmgn.py
import time
from typing import Dict, List, Optional, Any
import logging
from utils.base_client import BaseAPIClient
from utils.error_handling import (
    exponential_backoff, safe_float, safe_int, validate_token_address,
    InsufficientFundsException, InvalidTokenException
)
from config import config

logger = logging.getLogger(__name__)

class GMGNClient(BaseAPIClient):
    """Enhanced GMGN API client with comprehensive error handling"""
    
    def __init__(self):
        super().__init__(
            base_url=config.API_URLS["gmgn"],
            api_key=config.API_KEYS["gmgn"],
            service_name="gmgn",
            requests_per_minute=config.RATE_LIMITS["gmgn"]
        )
        self.authenticated = False
        self.wallet_balance = 0.0
        self.positions: Dict[str, Dict] = {}
    
    def authenticate_telegram(self, telegram_token: str) -> bool:
        """Authenticate with Telegram"""
        try:
            response = self.post('auth/telegram', {
                'token': telegram_token
            })
            self.authenticated = response.get('success', False)
            logger.info(f"Telegram authentication: {'success' if self.authenticated else 'failed'}")
            return self.authenticated
        except Exception as e:
            logger.error(f"Telegram authentication failed: {str(e)}")
            return False
    
    def authenticate_wallet(self, wallet_address: str, private_key: str = None) -> bool:
        """Authenticate wallet"""
        try:
            payload = {'wallet_address': wallet_address}
            if private_key:
                payload['private_key'] = private_key
            
            response = self.post('auth/wallet', payload)
            self.authenticated = response.get('success', False)
            
            if self.authenticated:
                self.wallet_balance = safe_float(response.get('balance', 0))
                logger.info(f"Wallet authentication successful. Balance: ${self.wallet_balance}")
            else:
                logger.error("Wallet authentication failed")
            
            return self.authenticated
        except Exception as e:
            logger.error(f"Wallet authentication failed: {str(e)}")
            return False
    
    def get_wallet_balance(self) -> float:
        """Get current wallet balance"""
        try:
            response = self.get('wallet/balance')
            self.wallet_balance = safe_float(response.get('balance', 0))
            return self.wallet_balance
        except Exception as e:
            logger.error(f"Failed to get wallet balance: {str(e)}")
            return 0.0
    
    def place_order(self, token_address: str, side: str, quantity: float, 
                   order_type: str = "market", limit_price: Optional[float] = None, 
                   slippage: float = 0.01) -> Dict[str, Any]:
        """
        Place a trading order with comprehensive validation
        
        Args:
            token_address: Token contract address
            side: 'buy' or 'sell'
            quantity: Amount to trade
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            slippage: Maximum slippage tolerance
            
        Returns:
            Order confirmation data
        """
        if not self.authenticated:
            raise APIException("Not authenticated with GMGN")
        
        if not validate_token_address(token_address):
            raise InvalidTokenException(f"Invalid token address: {token_address}")
        
        if side not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")
        
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if order_type == 'limit' and limit_price is None:
            raise ValueError("Limit price required for limit orders")
        
        # Check balance for buy orders
        if side == 'buy':
            current_balance = self.get_wallet_balance()
            estimated_cost = quantity * (limit_price or self._get_current_price(token_address))
            
            if estimated_cost > current_balance:
                raise InsufficientFundsException(
                    f"Insufficient balance: ${current_balance} < ${estimated_cost}"
                )
        
        # Check position for sell orders
        if side == 'sell':
            position = self.get_position(token_address)
            if position.get('quantity', 0) < quantity:
                raise InsufficientFundsException(
                    f"Insufficient position: {position.get('quantity', 0)} < {quantity}"
                )
        
        payload = {
            "token_address": token_address,
            "side": side,
            "quantity": quantity,
            "type": order_type,
            "slippage": slippage,
        }
        
        if order_type == "limit":
            payload["limit_price"] = limit_price
        
        try:
            response = self.post('orders', payload)
            order_id = response.get('order_id')
            
            logger.info(
                f"Order placed: {side} {quantity} {token_address} "
                f"(Order ID: {order_id})"
            )
            
            # Log to trading logger
            trading_logger = logging.getLogger('trading')
            trading_logger.info(
                f"ORDER_PLACED,{order_id},{side},{token_address},{quantity},"
                f"{order_type},{limit_price or 'market'},{slippage}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to place order: {str(e)}")
            raise
    
    def check_order_status(self, order_id: str) -> Dict[str, Any]:
        """Check order status"""
        try:
            response = self.get(f'orders/{order_id}')
            return response
        except Exception as e:
            logger.error(f"Failed to check order status for {order_id}: {str(e)}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        try:
            response = self.delete(f'orders/{order_id}')
            success = response.get('success', False)
            
            if success:
                logger.info(f"Order {order_id} cancelled successfully")
                trading_logger = logging.getLogger('trading')
                trading_logger.info(f"ORDER_CANCELLED,{order_id}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {str(e)}")
            return False
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        try:
            response = self.get('orders/open')
            return response.get('orders', [])
        except Exception as e:
            logger.error(f"Failed to get open orders: {str(e)}")
            return []
    
    def get_position(self, token_address: str) -> Dict[str, Any]:
        """Get position for a specific token"""
        try:
            response = self.get(f'positions/{token_address}')
            position = response.get('position', {})
            
            # Cache position locally
            self.positions[token_address] = position
            
            return position
        except Exception as e:
            logger.error(f"Failed to get position for {token_address}: {str(e)}")
            return {}
    
    def get_all_positions(self) -> List[Dict]:
        """Get all current positions"""
        try:
            response = self.get('positions')
            positions = response.get('positions', [])
            
            # Update local cache
            for position in positions:
                token_address = position.get('token_address')
                if token_address:
                    self.positions[token_address] = position
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {str(e)}")
            return []
    
    def fetch_smart_trades(self, min_value: float = 1000, 
                          limit: int = 100) -> Dict[str, Any]:
        """Fetch smart money trades"""
        try:
            params = {
                'min_value': min_value,
                'limit': limit
            }
            response = self.get('smartmoney/trades', params)
            return response
        except Exception as e:
            logger.error(f"Failed to fetch smart trades: {str(e)}")
            return {'trades': []}
    
    def fetch_wallet_tags(self, wallet_address: str) -> Dict[str, Any]:
        """Fetch wallet tags and classification"""
        try:
            response = self.get(f'wallets/{wallet_address}/tags')
            return response
        except Exception as e:
            logger.error(f"Failed to fetch wallet tags for {wallet_address}: {str(e)}")
            return {'tags': []}
    
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get detailed token information"""
        try:
            response = self.get(f'tokens/{token_address}')
            return response.get('token', {})
        except Exception as e:
            logger.error(f"Failed to get token info for {token_address}: {str(e)}")
            return {}
    
    def _get_current_price(self, token_address: str) -> float:
        """Get current token price"""
        try:
            token_info = self.get_token_info(token_address)
            return safe_float(token_info.get('price_usd', 0))
        except Exception as e:
            logger.warning(f"Failed to get current price for {token_address}: {str(e)}")
            return 0.0
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get trading history"""
        try:
            params = {'limit': limit}
            response = self.get('trades/history', params)
            return response.get('trades', [])
        except Exception as e:
            logger.error(f"Failed to get trade history: {str(e)}")
            return []
    
    def health_check(self) -> bool:
        """Check GMGN API health"""
        try:
            response = self.get('health')
            return response.get('status') == 'ok'
        except Exception:
            return False