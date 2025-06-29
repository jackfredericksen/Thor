# utils/rate_limiter.py
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_minute / 60.0
        self.bucket_size = max(1, requests_per_minute // 4)  # Burst capacity
        self.tokens = self.bucket_size
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens from the bucket

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait for tokens

        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill_bucket()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                # Calculate time until next token
                time_for_tokens = (tokens - self.tokens) / self.requests_per_second

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                time_for_tokens = min(time_for_tokens, timeout - elapsed)

            # Wait for tokens
            sleep_time = min(time_for_tokens, 1.0)  # Max 1 second sleep
            time.sleep(sleep_time)

    def _refill_bucket(self):
        """Refill the token bucket based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.requests_per_second
        self.tokens = min(self.bucket_size, self.tokens + tokens_to_add)
        self.last_refill = now


class GlobalRateLimiter:
    """Global rate limiter for managing multiple API endpoints"""

    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        self.lock = threading.Lock()

    def get_limiter(self, service: str, requests_per_minute: int) -> RateLimiter:
        """Get or create a rate limiter for a service"""
        with self.lock:
            if service not in self.limiters:
                self.limiters[service] = RateLimiter(requests_per_minute)
                logger.debug(
                    f"Created rate limiter for {service}: {requests_per_minute} req/min"
                )
            return self.limiters[service]

    def acquire(
        self,
        service: str,
        requests_per_minute: int,
        tokens: int = 1,
        timeout: Optional[float] = 30.0,
    ) -> bool:
        """Acquire tokens for a specific service"""
        limiter = self.get_limiter(service, requests_per_minute)

        start_time = time.time()
        success = limiter.acquire(tokens, timeout)

        if success:
            elapsed = time.time() - start_time
            if elapsed > 1.0:  # Log if we waited more than 1 second
                logger.info(
                    f"Rate limited {service}: waited {elapsed:.2f}s for {tokens} tokens"
                )
        else:
            logger.warning(f"Rate limit timeout for {service} after {timeout}s")

        return success


# Global rate limiter instance
rate_limiter = GlobalRateLimiter()


def rate_limited(
    service: str, requests_per_minute: int, tokens: int = 1, timeout: float = 30.0
):
    """
    Decorator for rate limiting function calls

    Args:
        service: Name of the service/API
        requests_per_minute: Rate limit for the service
        tokens: Number of tokens required for this call
        timeout: Maximum time to wait for rate limit
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not rate_limiter.acquire(service, requests_per_minute, tokens, timeout):
                raise Exception(f"Rate limit timeout for {service}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


class RequestTracker:
    """Track API request statistics"""

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def record_request(
        self, service: str, success: bool = True, response_time: Optional[float] = None
    ):
        """Record an API request"""
        now = time.time()

        with self.lock:
            # Clean old entries
            cutoff = now - (self.window_minutes * 60)
            while (
                self.requests[service]
                and self.requests[service][0]["timestamp"] < cutoff
            ):
                self.requests[service].popleft()

            # Add new entry
            self.requests[service].append(
                {"timestamp": now, "success": success, "response_time": response_time}
            )

    def get_stats(self, service: str) -> Dict:
        """Get request statistics for a service"""
        with self.lock:
            requests = list(self.requests[service])

        if not requests:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "requests_per_minute": 0.0,
            }

        total = len(requests)
        successful = sum(1 for r in requests if r["success"])
        failed = total - successful

        response_times = [
            r["response_time"] for r in requests if r["response_time"] is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        # Calculate requests per minute
        if total > 0:
            time_span = requests[-1]["timestamp"] - requests[0]["timestamp"]
            requests_per_minute = total / max(time_span / 60, 1)
        else:
            requests_per_minute = 0.0

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_response_time": avg_response_time,
            "requests_per_minute": requests_per_minute,
        }


# Global request tracker
request_tracker = RequestTracker()
