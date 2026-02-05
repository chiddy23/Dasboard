"""Rate limiting middleware to prevent brute force attacks."""

import time
from functools import wraps
from flask import request, jsonify
from collections import defaultdict
from threading import Lock
from config import Config


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 1 minute window
        self.requests = defaultdict(list)
        self.lock = Lock()

    def _get_client_id(self) -> str:
        """Get a unique identifier for the client."""
        # Use IP address as identifier
        # In production, consider X-Forwarded-For header for proxied requests
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or 'unknown'

    def _cleanup_old_requests(self, client_id: str, current_time: float):
        """Remove requests older than the window size."""
        cutoff = current_time - self.window_size
        self.requests[client_id] = [
            timestamp for timestamp in self.requests[client_id]
            if timestamp > cutoff
        ]

    def is_rate_limited(self) -> bool:
        """
        Check if the current request should be rate limited.

        Returns:
            True if rate limited, False otherwise
        """
        client_id = self._get_client_id()
        current_time = time.time()

        with self.lock:
            self._cleanup_old_requests(client_id, current_time)

            if len(self.requests[client_id]) >= self.requests_per_minute:
                return True

            self.requests[client_id].append(current_time)
            return False

    def get_remaining_requests(self) -> int:
        """
        Get the number of remaining requests for the current client.

        Returns:
            Number of remaining requests
        """
        client_id = self._get_client_id()
        current_time = time.time()

        with self.lock:
            self._cleanup_old_requests(client_id, current_time)
            return max(0, self.requests_per_minute - len(self.requests[client_id]))

    def get_reset_time(self) -> int:
        """
        Get seconds until the rate limit resets.

        Returns:
            Seconds until reset
        """
        client_id = self._get_client_id()

        with self.lock:
            if not self.requests[client_id]:
                return 0

            oldest_request = min(self.requests[client_id])
            reset_time = oldest_request + self.window_size - time.time()
            return max(0, int(reset_time))


# Global rate limiter instance
login_rate_limiter = RateLimiter(
    requests_per_minute=Config.RATE_LIMIT_PER_MINUTE
)


def rate_limit(limiter: RateLimiter = None):
    """
    Decorator to apply rate limiting to a route.

    Args:
        limiter: RateLimiter instance to use (defaults to login_rate_limiter)
    """
    if limiter is None:
        limiter = login_rate_limiter

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if limiter.is_rate_limited():
                reset_time = limiter.get_reset_time()
                return jsonify({
                    'success': False,
                    'error': 'Too many requests. Please try again later.',
                    'code': 'RATE_LIMITED',
                    'retryAfter': reset_time
                }), 429

            response = f(*args, **kwargs)

            # Add rate limit headers to response
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Remaining'] = str(limiter.get_remaining_requests())
                response.headers['X-RateLimit-Reset'] = str(limiter.get_reset_time())

            return response

        return decorated_function

    return decorator
