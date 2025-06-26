# utils/base_client.py
import time
import requests
from typing import Optional, Dict, Any
import logging
from utils.error_handling import (
    exponential_backoff, handle_api_response, CircuitBreaker,
    APIException, RateLimitException
)
from utils.rate_limiter import rate_limited, request_tracker

logger = logging.getLogger(__name__)

class BaseAPIClient:
    """Enhanced base class for API clients with error handling and rate limiting"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, 
                 service_name: str = "API", requests_per_minute: int = 60,
                 timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.service_name = service_name
        self.requests_per_minute = requests_per_minute
        self.timeout = timeout
        
        # Setup session
        self.session = requests.Session()
        self.session.timeout = timeout
        
        # Set headers
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'User-Agent': 'DexTradingBot/1.0'
            })
        
        # Circuit breaker for this client
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=300)
    
    @exponential_backoff(max_retries=3, base_delay=1.0)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """
        Make HTTP request with error handling and rate limiting
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests
            
        Returns:
            Parsed JSON response
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Apply rate limiting
        @rate_limited(self.service_name, self.requests_per_minute)
        @self.circuit_breaker
        def make_request():
            start_time = time.time()
            try:
                logger.debug(f"Making {method} request to {url}")
                response = self.session.request(method, url, **kwargs)
                
                response_time = time.time() - start_time
                request_tracker.record_request(
                    self.service_name, 
                    success=response.status_code < 400,
                    response_time=response_time
                )
                
                return handle_api_response(response, self.service_name)
                
            except requests.exceptions.RequestException as e:
                response_time = time.time() - start_time
                request_tracker.record_request(
                    self.service_name, 
                    success=False,
                    response_time=response_time
                )
                logger.error(f"{self.service_name} request failed: {str(e)}")
                raise APIException(f"{self.service_name} request failed: {str(e)}")
        
        return make_request()
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[Any, Any]:
        """Make GET request"""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, json_data: Optional[Dict] = None, 
             data: Optional[Dict] = None) -> Dict[Any, Any]:
        """Make POST request"""
        return self._make_request('POST', endpoint, json=json_data, data=data)
    
    def put(self, endpoint: str, json_data: Optional[Dict] = None) -> Dict[Any, Any]:
        """Make PUT request"""
        return self._make_request('PUT', endpoint, json=json_data)
    
    def delete(self, endpoint: str) -> Dict[Any, Any]:
        """Make DELETE request"""
        return self._make_request('DELETE', endpoint)
    
    def get_stats(self) -> Dict:
        """Get API usage statistics"""
        return request_tracker.get_stats(self.service_name)
    
    def health_check(self) -> bool:
        """Check if the API is healthy"""
        try:
            # Most APIs have a health or status endpoint
            # Override this method in specific clients
            self.get('health')
            return True
        except Exception as e:
            logger.warning(f"{self.service_name} health check failed: {str(e)}")
            return False