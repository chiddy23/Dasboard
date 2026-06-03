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

# Tiered retry to avoid the cross-request token war.
#
# Old design: any 401 → /Authenticate(chad) → mint a fresh token → retry.
# Problem: if a big dept fetch is currently fanning out 28 enrollment workers
# elsewhere in the process, that /Authenticate REVOKES their token. They all
# 401, return None, and the dept comes back partial — e.g. Spencer 519/1302.
#
# New design: first try inline-retry with the SAME token (handles Absorb's
# transient per-call LB 401s without touching the auth state at all). Only
# escalate to a real refresh if the token genuinely seems dead.
_INLINE_RETRIES = 2          # cheap retries with same token
_INLINE_BACKOFF_SECONDS = 0.4
_REFRESH_RETRIES = 1         # phase 2: refresh + retry
_REFRESH_BACKOFF_SECONDS = 0.6
# Phase 3 (last resort): after phase 2 fails, wait for the debounce window
# to fully expire and try refreshing again. This recovers from chad's per-
# call DOA state where a freshly-minted token dies on first use — the wait
# lets Absorb's account state cool slightly AND ensures the next refresh
# actually mints (vs the debounce reusing the dead one).
_PHASE3_DELAY_SECONDS = 3.0
_PHASE3_RETRIES = 1


def absorb_retry_on_401(f):
    """Decorator: tolerate 401s on routes that hit Absorb.

    Strategy:
      1. Run the route.
      2. On 401, retry inline up to _INLINE_RETRIES times with the same
         token. Absorb's load balancer throws transient per-call 401s under
         load — sleeping briefly and retrying recovers most of these without
         minting a new token.
      3. If still failing, escalate ONCE: refresh the token and retry. This
         minting can revoke other in-flight requests' tokens, so we only do
         it when inline-retry has clearly failed (token genuinely dead).
      4. Otherwise propagate.

    Apply AFTER @login_required:
        @route(...)
        @login_required
        @absorb_retry_on_401
        def my_route():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        from absorb_api import AbsorbAPIError
        from routes.dashboard import _refresh_user_absorb_token

        # Phase 1: inline retries with same token (no /Authenticate).
        for _attempt in range(1 + _INLINE_RETRIES):
            try:
                return f(*args, **kwargs)
            except AbsorbAPIError as e:
                if e.status_code != 401:
                    raise
                if _attempt < _INLINE_RETRIES:
                    if _INLINE_BACKOFF_SECONDS:
                        time.sleep(_INLINE_BACKOFF_SECONDS)
                    continue

        # Phase 2: escalate to real refresh. Last resort because the new
        # token revokes everyone else's chad session in this process.
        for _attempt in range(_REFRESH_RETRIES):
            if not _refresh_user_absorb_token():
                # Refresh failed (no creds / zombie) — give up.
                raise AbsorbAPIError("Session expired. Please log in again.", 401)
            if _REFRESH_BACKOFF_SECONDS:
                time.sleep(_REFRESH_BACKOFF_SECONDS)
            try:
                return f(*args, **kwargs)
            except AbsorbAPIError as e:
                if e.status_code != 401:
                    raise
                # try refresh again on the next loop iteration

        # Phase 3: chad is in per-call DOA back-pressure (refresh-minted
        # token died on first use). Wait past the debounce window so the
        # next refresh attempt mints a genuinely fresh token, then try
        # once more. This recovers the modal-fails-5x-in-a-row pattern.
        for _attempt in range(_PHASE3_RETRIES):
            time.sleep(_PHASE3_DELAY_SECONDS)
            if not _refresh_user_absorb_token():
                raise AbsorbAPIError("Session expired. Please log in again.", 401)
            try:
                return f(*args, **kwargs)
            except AbsorbAPIError as e:
                if e.status_code != 401:
                    raise

        # Out of escalation attempts.
        raise AbsorbAPIError("Session expired. Please log in again.", 401)
    return wrapper
