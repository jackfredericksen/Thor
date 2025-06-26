# utils/error_handling.py
import time
import random
import functools
import logging
from typing import Callable, Any, Optional, Tuple, Type
import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout

logger = logging.getLogger(__name__)

class TradingBotException(Exception):
    """Base exception for trading bot"""
    pass

class APIException(TradingBotException):
    """API related exceptions"""
    pass

class RateLimitException(APIException):
    """Rate limit exceeded"""
    pass

class InsufficientFundsException(TradingBotException):
    """Insufficient funds for trading"""
    pass

class InvalidTokenException(TradingBotException):
    """Invalid or unsupported token"""
    pass

def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (RequestException, APIException)
):
    """
    Decorator for exponential backoff retry logic
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Factor by which delay increases
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries. "
                            f"Last error: {str(e)}"
                        )
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
                except Exception as e:
                    # Don't retry for unexpected exceptions
                    logger.error(f"{func.__name__} failed with unexpected error: {str(e)}")
                    raise e
            
            # Should never reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator

def handle_api_response(response: requests.Response, service_name: str = "API") -> dict:
    """
    Handle API response with proper error checking
    
    Args:
        response: requests.Response object
        service_name: Name of the API service for logging
        
    Returns:
        Parsed JSON response
        
    Raises:
        RateLimitException: If rate limited
        APIException: For other API errors
    """
    try:
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        status_code = response.status_code
        
        if status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            logger.warning(f"{service_name} rate limited. Retry after {retry_after} seconds")
            raise RateLimitException(f"Rate limited by {service_name}. Retry after {retry_after}s")
        elif status_code >= 500:
            logger.error(f"{service_name} server error: {status_code}")
            raise APIException(f"{service_name} server error: {status_code}")
        elif status_code >= 400:
            logger.error(f"{service_name} client error: {status_code} - {response.text}")
            raise APIException(f"{service_name} client error: {status_code}")
        else:
            raise APIException(f"{service_name} HTTP error: {status_code}")
    except ValueError as e:
        logger.error(f"{service_name} returned invalid JSON: {str(e)}")
        raise APIException(f"{service_name} returned invalid JSON")

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def validate_token_address(address: str) -> bool:
    """Validate Ethereum token address format"""
    if not address or not isinstance(address, str):
        return False
    
    # Remove 0x prefix if present
    address = address.lower()
    if address.startswith('0x'):
        address = address[2:]
    
    # Check if it's 40 hex characters
    if len(address) != 40:
        return False
    
    try:
        int(address, 16)
        return True
    except ValueError:
        return False

class CircuitBreaker:
    """Circuit breaker pattern for API calls"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = 'HALF_OPEN'
                    logger.info(f"Circuit breaker for {func.__name__} entering HALF_OPEN state")
                else:
                    raise APIException(f"Circuit breaker OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
