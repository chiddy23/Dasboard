"""Absorb 401-retry decorator for Flask route handlers.

Placed in utils/ to avoid circular imports between routes/dashboard.py,
routes/students.py, and routes/exam.py (dashboard imports from exam,
exam/students would import from dashboard = circular).

The decorator catches AbsorbAPIError(401), refreshes the token via the
locked helper, and retries the route handler once. The actual refresh
helper is imported lazily inside the decorator to break the import cycle.
"""

from functools import wraps


def absorb_retry_on_401(f):
    """Decorator: if the wrapped route raises AbsorbAPIError with status 401,
    refresh the user's Absorb token once (using the locked helper) and retry
    the entire route handler. If the refresh fails or the retry also 401s,
    the error propagates normally.

    Apply to any @login_required route that calls Absorb APIs so that idle
    token expiry doesn't immediately kick the user to the login screen.

    This decorator must be placed AFTER @login_required:

        @route(...)
        @login_required
        @absorb_retry_on_401
        def my_route():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Lazy import to break circular dependency
        from absorb_api import AbsorbAPIError
        try:
            return f(*args, **kwargs)
        except AbsorbAPIError as e:
            if e.status_code != 401:
                raise
            # Lazy import of the refresh helper
            from routes.dashboard import _refresh_user_absorb_token
            if not _refresh_user_absorb_token():
                raise
            # Retry once with the refreshed token
            return f(*args, **kwargs)
    return wrapper
