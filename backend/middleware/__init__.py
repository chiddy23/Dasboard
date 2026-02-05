"""Middleware modules for JustInsurance Student Dashboard."""

from .auth_middleware import (
    login_required,
    get_current_user,
    get_current_department_id,
    get_absorb_token
)

from .rate_limiter import (
    RateLimiter,
    login_rate_limiter,
    rate_limit
)

__all__ = [
    'login_required',
    'get_current_user',
    'get_current_department_id',
    'get_absorb_token',
    'RateLimiter',
    'login_rate_limiter',
    'rate_limit'
]
