"""Absorb 401-retry decorator for Flask route handlers.

Placed in utils/ to avoid circular imports between routes/dashboard.py,
routes/students.py, and routes/exam.py (dashboard imports from exam,
exam/students would import from dashboard = circular).

The decorator catches AbsorbAPIError(401), refreshes the token via the
locked helper, and retries the route handler. The actual refresh helper
is imported lazily inside the decorator to break the import cycle.
"""

import time
from functools import wraps

# A route can make several sequential Absorb calls (the student-detail modal
# does get_users_by_department -> get_user_enrollments -> lesson/attempt
# fetches). Under Absorb's single-session-per-account model the token can be
# revoked again mid-route (e.g. another tab/deployment re-authed, or a fresh
# token hasn't propagated across Absorb's backend nodes yet). One retry isn't
# always enough, so retry a few times with a short backoff between attempts.
_MAX_401_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 0.6


def absorb_retry_on_401(f):
    """Decorator: if the wrapped route raises AbsorbAPIError(401), refresh the
    user's Absorb token (locked helper) and retry the whole route — up to
    _MAX_401_RETRIES times. If the refresh fails or all retries 401, the error
    propagates.

    Apply to any @login_required route that calls Absorb APIs so that token
    expiry (or a transient revocation) doesn't immediately kick the user to
    the login screen.

    Must be placed AFTER @login_required:

        @route(...)
        @login_required
        @absorb_retry_on_401
        def my_route():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Lazy imports to break circular dependency
        from absorb_api import AbsorbAPIError
        from routes.dashboard import _refresh_user_absorb_token

        attempt = 0
        while True:
            try:
                return f(*args, **kwargs)
            except AbsorbAPIError as e:
                if e.status_code != 401:
                    raise
                attempt += 1
                if attempt > _MAX_401_RETRIES:
                    # Exhausted retries — let it propagate.
                    raise
                if not _refresh_user_absorb_token():
                    # Can't refresh (no stored creds / refresh failed) — give up.
                    raise
                # Brief backoff so the freshly-minted token has time to
                # propagate across Absorb's backend before we retry.
                if _RETRY_BACKOFF_SECONDS:
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                # loop and retry the whole route
    return wrapper
