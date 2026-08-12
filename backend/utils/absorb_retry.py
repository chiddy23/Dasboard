"""Absorb 401-retry decorator for Flask route handlers.

Placed in utils/ to avoid circular imports between routes/dashboard.py,
routes/students.py, and routes/exam.py (dashboard imports from exam,
exam/students would import from dashboard = circular).

The decorator catches AbsorbAPIError(401), refreshes the token via the
locked helper, and retries the route handler. The actual refresh helper
is imported lazily inside the decorator to break the import cycle.
"""

import time
import random
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
#
# Backoffs are JITTERED per the Absorb pacing guide (their gateway is a
# token bucket refreshed every second; ~0.8s base clears a transient
# throttle, and jitter prevents concurrent retries from firing in sync and
# re-throttling — "the jitter is the important part", their dev team).
# Retry COUNTS are settled and unchanged; only the pacing moved.
_INLINE_RETRIES = 2          # cheap retries with same token
_INLINE_BACKOFF_BASE = 0.8   # x 2^attempt, + jitter below
_JITTER_MAX = 0.4
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
        # Jittered exponential: 0.8s, 1.6s (+0-0.4s jitter each) — a transient
        # gateway throttle clears within ~1s, and the jitter keeps concurrent
        # routes from re-throttling each other with synchronized retries.
        for _attempt in range(1 + _INLINE_RETRIES):
            try:
                return f(*args, **kwargs)
            except AbsorbAPIError as e:
                if e.status_code != 401:
                    raise
                if _attempt < _INLINE_RETRIES:
                    time.sleep(_INLINE_BACKOFF_BASE * (2 ** _attempt)
                               + random.uniform(0, _JITTER_MAX))
                    continue

        # Phases 2+3 REMOVED (2026-08-12): the decorator used to refresh —
        # i.e. MINT — when inline retries failed. That made every data
        # request a potential assassin: an abandoned request (F5, logout,
        # superseded loader run) could mint minutes later and revoke the
        # live session's token — the entire token-war class of 2026-08-12.
        # Data paths never mint now. The single mint authority is
        # POST /api/auth/refresh-token, called single-flight by the
        # frontend; a persistent 401 propagates to the client, which
        # refreshes once and retries the call with the new cookie.
        raise AbsorbAPIError("Session expired. Please log in again.", 401)
    return wrapper
