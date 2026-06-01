"""Dashboard routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g, request
from functools import wraps
import re
import sys
import os
import tempfile
import threading
import hashlib
import requests as _requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import session
from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils import format_student_for_response, get_status_from_last_login
from utils.credential_store import decrypt_password
from config import Config
from routes.exam import invalidate_exam_absorb_cache, get_department_name
from snapshot_db import get_user_dept_prefs, save_user_dept_prefs, get_user_hidden_students, save_user_hidden_students, get_user_ghl_settings, get_user_ghl_settings_masked, save_user_ghl_settings, get_user_bitrix_settings, get_user_bitrix_settings_masked, save_user_bitrix_settings, get_user_sheet_settings, get_user_sheet_settings_masked, save_user_sheet_settings
from demo_data import (
    is_demo_dept, DEMO_DEPT_ID, DEMO_DEPT_NAME,
    get_cached_demo_students
)

# Optional POSIX file-lock support for cross-process token-refresh
# coordination. Gunicorn runs 4 worker processes, so an in-process
# threading.Lock alone is not enough — two different gunicorn workers
# could both try to re-auth concurrently, each invalidating the other's
# token (Absorb uses single-session-per-account: calling /Authenticate
# revokes all previous tokens for this user). fcntl.flock gives us a
# real cross-process mutex on Linux (where Render runs). On Windows
# dev boxes fcntl isn't available and we fall back to threading-lock
# only — acceptable because local dev is single-worker.
try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

dashboard_bp = Blueprint('dashboard', __name__)

# Simple in-memory cache for student data (per department)
# Structure: {department_id: {'data': [...], 'timestamp': datetime, 'formatted': [...]}}
_student_cache = {}
CACHE_TTL_MINUTES = 5  # Cache data for 5 minutes

# Per-department FETCH lock. Absorb uses a single-session-per-account token, so
# only ONE /Authenticate may be "live" at a time. On a cold cache, /students and
# /summary (and any extra tabs) BOTH fall through to a fresh fetch at the same
# instant; on a large dept each fans out into many parallel /users calls and the
# two concurrent fetches re-authenticate + revoke each other's token mid-flight.
# That's exactly the "bucket failed: Session expired" storm and the "N skipped
# due to errors" / "missing 295 users" we see on big departments. Serialize the
# FETCH per dept: the first caller fetches + caches, the rest wait then read the
# warm cache. Only the fetch is guarded — warm-cache reads stay lock-free, so
# the common case (data already cached) is unaffected.
_fetch_locks = {}
_fetch_locks_guard = threading.Lock()


def _get_fetch_lock(department_id):
    """Return (creating on first use) the per-department fetch lock."""
    with _fetch_locks_guard:
        lk = _fetch_locks.get(department_id)
        if lk is None:
            lk = threading.Lock()
            _fetch_locks[department_id] = lk
        return lk


def _read_fresh_cache(department_id, by_sibling=False):
    """Return (data, formatted) if a non-expired cache entry exists, else None."""
    entry = _student_cache.get(department_id)
    if not entry:
        return None
    age = datetime.utcnow() - entry['timestamp']
    if age < timedelta(minutes=CACHE_TTL_MINUTES):
        if by_sibling:
            print(f"[CACHE] Using cached data for {department_id} (filled by concurrent fetch)")
        else:
            print(f"[CACHE] Using cached data for {department_id} (age: {age.seconds}s)")
        return entry['data'], entry['formatted']
    return None


def get_cached_students(department_id, token):
    """Get students from cache or fetch fresh data."""
    # Demo mode — serve static anonymized data (zero API calls)
    if is_demo_dept(department_id):
        cached = get_cached_demo_students()
        formatted = [format_student_for_response(s) for s in cached]
        formatted.sort(key=lambda s: (s['status']['priority'], -s['progress']['value']))
        return cached, formatted

    # Fast path: a valid cache entry needs no lock (keep concurrent reads cheap).
    cached = _read_fresh_cache(department_id)
    if cached is not None:
        return cached

    # Cold/expired cache: serialize the fetch per dept so concurrent callers
    # don't each launch a full parallel dept fetch and revoke each other's
    # single-session Absorb token. Use a generous acquire timeout so a single
    # slow fetch can't wedge the worker — if we can't get the lock in time we
    # fall through and fetch anyway (degraded, never deadlocked).
    lock = _get_fetch_lock(department_id)
    acquired = lock.acquire(timeout=110)
    try:
        if acquired:
            # A sibling fetch may have populated the cache while we waited.
            cached = _read_fresh_cache(department_id, by_sibling=True)
            if cached is not None:
                return cached

        # Fetch fresh data (holding the per-dept lock — no sibling races).
        print(f"[CACHE] Fetching fresh data for {department_id}")
        client = AbsorbAPIClient()
        client.set_token(token)
        students = client.get_students_with_progress(department_id)

        # Format students
        formatted_students = [format_student_for_response(student) for student in students]

        # Sort by status priority (re-engage first), then by progress
        formatted_students.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        # Store in cache
        _student_cache[department_id] = {
            'data': students,
            'formatted': formatted_students,
            'timestamp': datetime.utcnow()
        }

        return students, formatted_students
    finally:
        if acquired:
            lock.release()


def invalidate_cache(department_id):
    """Clear cache for a department."""
    if department_id in _student_cache:
        del _student_cache[department_id]
        print(f"[CACHE] Invalidated cache for {department_id}")


# Per-process threading lock that serializes re-auth within a single
# gunicorn worker. Guards against same-process double-refresh races.
_refresh_lock = threading.Lock()

# Process-global "latest known token" per user. CRITICAL for the CAS in
# _refresh_user_absorb_token: Flask-Session is request-scoped (each request
# loads its OWN snapshot of the session from the filesystem store), so the
# session-based CAS can't see a refresh a CONCURRENT request just performed.
# Without this, two simultaneous requests (e.g. the dashboard's /summary +
# /students on a cold load) each re-authenticate, and since Absorb is
# single-session-per-account, each re-auth revokes the other's token -> an
# endless refresh/401 ping-pong (the app waging a token war with ITSELF). This
# in-memory map is shared across all threads in the worker, so a sibling's
# fresh token is visible immediately. Accessed only under _refresh_lock.
_latest_user_tokens = {}

# Process-global set of currently-logged-in users. Updated by login (add) and
# logout (remove). Read by _refresh_user_absorb_token — if a user has logged
# out, their in-flight requests (which Flask doesn't abort on client
# disconnect) must NOT re-Authenticate, because that would mint a fresh chad
# token that revokes the NEXT login's token. That's the "first login boots me,
# second works 10s later" pattern — the zombie retry loop from attempt 1 wars
# with attempt 2's fresh token. Bailing out of refresh kills the zombie.
_active_user_logins = set()
_active_logins_lock = threading.Lock()


def _refresh_lock_path(user_email: str) -> str:
    """Return a per-user lockfile path for cross-process coordination.
    Tied to SECRET_KEY so the path is non-guessable and stable across
    a single Render deploy lifetime."""
    if not user_email:
        user_email = 'anon'
    key_seed = f"{Config.SECRET_KEY or ''}:{user_email.lower().strip()}"
    digest = hashlib.sha256(key_seed.encode('utf-8')).hexdigest()[:20]
    return os.path.join(tempfile.gettempdir(), f"absorb_refresh_{digest}.lock")


def _refresh_user_absorb_token():
    """Transparently re-authenticate the current user with Absorb using
    their own credentials stored (encrypted) in the Flask session at login.

    CONCURRENCY: Absorb uses a single-session-per-account model — calling
    /Authenticate revokes the previous token for this user. If TWO threads
    or TWO gunicorn workers call this function concurrently, each mints a
    new token and each invalidates the other's, leaving at least one
    request holding a dead token. This manifests as "Session expired"
    errors mid-fetch after a successful refresh.

    Protection strategy (two layers):

      1. In-process threading.Lock — serializes refreshes within a single
         gunicorn worker. Always applied.

      2. Per-user file lock via fcntl.flock — serializes refreshes across
         gunicorn worker PROCESSES on Linux (Render). Lock file path is
         derived from SECRET_KEY + user email. On Windows (dev) fcntl
         is unavailable and we fall back to threading-lock only, which is
         acceptable because local dev is single-worker.

    Compare-and-swap: once both locks are held we re-read the session to
    see if a sibling refresh already produced a fresh token while we were
    waiting. If yes we reuse it instead of minting another (avoiding the
    clobber chain).

    On success: updates session['user']['token'] + tokenExpiresAt, updates
    g.absorb_token, returns True. Refreshed token belongs to the user
    themselves — tenant isolation preserved.
    On failure (no stored creds, wrong password, Absorb down): returns
    False and the caller should surface the current "please log in again"
    message.
    """
    user_data = session.get('user') if session else None
    if not user_data:
        return False

    # Remember the token we entered with so the CAS check (after we
    # acquire the locks) can detect whether a sibling refresh happened
    # while we waited.
    entry_token = user_data.get('token')
    username = user_data.get('username') or user_data.get('email')
    if not username:
        print('[TOKEN REFRESH] No username in session — cannot refresh')
        return False

    # Zombie-request guard. Flask doesn't abort in-flight requests when the
    # browser disconnects, so an /students request that 401-stormed during
    # attempt 1 can still be cycling through its retry loop AFTER the user
    # has clicked logout AND logged in again. If we /Authenticate from that
    # zombie now, we mint a fresh chad token that REVOKES the next login's
    # token, causing attempt 2 to also fail. Check the process-global active-
    # logins set: if this user is NO LONGER logged in (logout cleared them),
    # the request is a zombie — bail without re-Auth-ing.
    uname_key_check = (username or '').lower().strip()
    with _active_logins_lock:
        still_active = uname_key_check in _active_user_logins
    if not still_active:
        print(f'[TOKEN REFRESH] Skipping refresh — user {uname_key_check} is no longer logged in (zombie request)')
        return False

    lock_path = _refresh_lock_path(username)
    lock_file = None

    # Acquire in-process lock first (fast). This serializes threads within
    # the same gunicorn worker.
    with _refresh_lock:
        # Then acquire the file lock (cross-process serialization on Linux).
        if _HAS_FCNTL:
            try:
                lock_file = open(lock_path, 'w')
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except Exception as e:
                print(f'[TOKEN REFRESH] flock acquire failed ({type(e).__name__}), proceeding without cross-process lock')
                if lock_file is not None:
                    try:
                        lock_file.close()
                    except Exception:
                        pass
                lock_file = None

        try:
            # CAS: re-read the session inside the lock. If another worker
            # already refreshed while we waited, the session token has
            # changed — reuse it without minting another.
            current_user_data = session.get('user') or {}
            current_token = current_user_data.get('token')
            if current_token and current_token != entry_token:
                g.absorb_token = current_token
                print(f'[TOKEN REFRESH] CAS hit — sibling refresh detected, reusing their token')
                return True

            # Cross-request CAS: the session read above is THIS request's own
            # snapshot and won't reflect a refresh a concurrent request just
            # did (filesystem sessions are request-scoped). Check the
            # process-global token too — if a sibling already minted a newer
            # token, reuse it instead of re-authing (which would revoke theirs
            # and kick off the refresh/401 ping-pong).
            uname_key = (username or '').lower().strip()
            shared_token = _latest_user_tokens.get(uname_key)
            if shared_token and shared_token != entry_token:
                g.absorb_token = shared_token
                current_user_data['token'] = shared_token
                session['user'] = current_user_data
                session.modified = True
                print('[TOKEN REFRESH] CAS hit (shared in-memory token) — reusing concurrent refresh')
                return True

            # No sibling refresh — proceed with actual re-auth.
            enc_pwd = current_user_data.get('absorbPasswordEnc')
            if not enc_pwd:
                print('[TOKEN REFRESH] No stored credentials in session — cannot refresh')
                return False

            password = decrypt_password(enc_pwd, Config.SECRET_KEY)
            if not password:
                print('[TOKEN REFRESH] Could not decrypt stored password '
                      '(SECRET_KEY changed since login?) — cannot refresh')
                return False

            try:
                client = AbsorbAPIClient()
                auth_result = client.authenticate_user(username, password)
            except Exception as e:
                # Do NOT log the exception body — could echo back the
                # request which may contain the password.
                print(f'[TOKEN REFRESH] Absorb auth failed: {type(e).__name__}')
                password = None
                return False
            finally:
                password = None  # best-effort local wipe

            if not auth_result or not auth_result.get('success'):
                print(f'[TOKEN REFRESH] Re-auth returned no success for {username} '
                      '(Absorb rejected or throttled the re-auth)')
                return False

            new_token = auth_result.get('token')
            if not new_token:
                print(f'[TOKEN REFRESH] Re-auth succeeded but returned empty token for {username}')
                return False

            new_expiry = datetime.utcnow() + timedelta(hours=4)
            current_user_data['token'] = new_token
            current_user_data['tokenExpiresAt'] = new_expiry.isoformat()
            session['user'] = current_user_data
            session.modified = True
            g.absorb_token = new_token
            # Publish to the process-global store so concurrent requests in this
            # worker reuse this token instead of re-authing (see _latest_user_tokens).
            _latest_user_tokens[(username or '').lower().strip()] = new_token
            print(f'[TOKEN REFRESH] Refreshed Absorb token for {username} (locked)')
            return True
        finally:
            if lock_file is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except Exception:
                    pass


def _fetch_depts_collect(dept_ids, token, sequential=False):
    """Fetch several departments and collect (all_formatted, dept_meta).

    Per-dept exceptions are swallowed into dept_meta entries with
    status='error' so callers can scan for specific failures (e.g. an
    expired Absorb token) and decide whether to retry.

    When sequential=True, depts are fetched one at a time instead of in
    parallel. This is used on the retry-after-token-refresh path because
    Absorb's single-session-per-account model needs a moment for the new
    token to propagate across their backend nodes — firing 3+ depts with
    parallel enrollment fan-outs immediately after a refresh can still
    hit stale nodes and 401. Sequential retry lets each dept complete
    fully before the next starts.
    """
    all_formatted = []
    dept_meta = []
    if not dept_ids:
        return all_formatted, dept_meta

    # Sequential mode OR single dept — same simple loop
    if sequential or len(dept_ids) == 1:
        for dept_id in dept_ids:
            try:
                meta, students = _fetch_dept_students(dept_id, token)
                dept_meta.append(meta)
                all_formatted.extend(students)
            except Exception as e:
                print(f"[FETCH] Error fetching {dept_id}: {e}")
                dept_meta.append({
                    'id': dept_id, 'name': None, 'studentCount': 0,
                    'status': 'error', 'error': str(e),
                })
        return all_formatted, dept_meta

    with ThreadPoolExecutor(max_workers=min(10, len(dept_ids))) as executor:
        future_to_dept = {
            executor.submit(_fetch_dept_students, dept_id, token): dept_id
            for dept_id in dept_ids
        }
        for future in as_completed(future_to_dept):
            dept_id = future_to_dept[future]
            try:
                meta, students = future.result()
                dept_meta.append(meta)
                all_formatted.extend(students)
            except Exception as e:
                print(f"[FETCH] Error fetching {dept_id}: {e}")
                dept_meta.append({
                    'id': dept_id, 'name': None, 'studentCount': 0,
                    'status': 'error', 'error': str(e),
                })
    return all_formatted, dept_meta


def _expired_dept_ids(dept_meta):
    """Return the list of dept IDs whose fetch failed with an Absorb
    'Session expired' error — candidates for a post-token-refresh retry."""
    out = []
    for m in dept_meta or []:
        if m.get('status') != 'error':
            continue
        err = (m.get('error') or '').lower()
        if 'session expired' in err or '401' in err:
            out.append(m.get('id'))
    return [d for d in out if d]


def _get_cached_students_with_retry(dept_id, max_retries=3):
    """Wrap get_cached_students with token refresh + retry on 401.

    Used by single-dept endpoints (/summary, /students) so the first
    request after login doesn't hard-crash the frontend with a 401 when a
    stale/just-revoked Absorb token is in play. Refreshes with the user's
    own stored credentials (tenant isolation preserved) and retries up to
    max_retries times with a short backoff — a freshly-minted token can be
    revoked again (another tab/deployment) or not yet propagated across
    Absorb's backend, so one retry isn't always enough.
    """
    import time as _time
    attempt = 0
    while True:
        try:
            return get_cached_students(dept_id, g.absorb_token)
        except AbsorbAPIError as e:
            if e.status_code != 401:
                raise
            attempt += 1
            if attempt > max_retries:
                raise
            if not _refresh_user_absorb_token():
                raise
            # Clear any partial/empty cache from the failed call so the retry
            # re-fetches instead of serving a cached empty list.
            invalidate_cache(dept_id)
            _time.sleep(0.6)


def get_quick_students(department_id, token):
    """Get basic student data quickly without enrollments."""
    # Check cache first
    if department_id in _student_cache:
        cache_entry = _student_cache[department_id]
        cache_age = datetime.utcnow() - cache_entry['timestamp']
        if cache_age < timedelta(minutes=CACHE_TTL_MINUTES):
            return cache_entry['formatted']

    # Get basic data only (fast)
    client = AbsorbAPIClient()
    client.set_token(token)
    students = client.get_students_basic(department_id)

    # Format students
    formatted = [format_student_for_response(student) for student in students]
    formatted.sort(key=lambda s: (s['status']['priority'], -s['progress']['value']), reverse=False)
    return formatted


@dashboard_bp.route('/summary/quick', methods=['GET'])
@login_required
def get_summary_quick():
    """
    Get quick summary (just student count and status from basic data).
    """
    try:
        formatted_students = get_quick_students(g.department_id, g.absorb_token)
        total = len(formatted_students)
        complete = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
        active = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
        warning = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
        reengage = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total,
                'completeCount': complete,
                'activeCount': active,
                'warningCount': warning,
                'reengageCount': reengage,
                'averageProgress': 0  # Will be updated with full load
            },
            'quick': True
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/summary', methods=['GET'])
@login_required
def get_summary():
    """
    Get dashboard summary with KPI data (uses cache).

    Returns:
        JSON response with summary statistics
    """
    try:
        # Get students from cache (formatted students have correct COMPLETE status)
        students, formatted_students = _get_cached_students_with_retry(g.department_id)

        # Calculate KPIs from formatted students (which have progress-aware status)
        total_students = len(formatted_students)
        complete_count = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
        active_count = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
        warning_count = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
        reengage_count = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')
        total_progress = sum(s['progress']['value'] for s in formatted_students)

        avg_progress = round(total_progress / total_students, 1) if total_students > 0 else 0

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total_students,
                'completeCount': complete_count,
                'activeCount': active_count,
                'warningCount': warning_count,
                'reengageCount': reengage_count,
                'averageProgress': avg_progress
            }
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch dashboard summary'
        }), 500


@dashboard_bp.route('/students/quick', methods=['GET'])
@login_required
def get_students_quick():
    """
    Get students quickly without enrollment data (fast initial load).
    """
    try:
        formatted_students = get_quick_students(g.department_id, g.absorb_token)
        return jsonify({
            'success': True,
            'students': formatted_students,
            'count': len(formatted_students),
            'quick': True
        })
    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch students: {str(e)}'
        }), 500


@dashboard_bp.route('/students', methods=['GET'])
@login_required
def get_students():
    """
    Get all students in the department with progress data (uses cache).

    Returns:
        JSON response with formatted student list
    """
    try:
        # Get students from cache
        _, formatted_students = _get_cached_students_with_retry(g.department_id)

        return jsonify({
            'success': True,
            'students': formatted_students,
            'count': len(formatted_students)
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        import traceback
        print(f"[ERROR] Students fetch failed: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to fetch students: {str(e)}'
        }), 500


GUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
MAX_EXTRA_DEPTS = 30


def _compute_summary(formatted_students):
    """Calculate KPI summary dict from a list of formatted students."""
    total = len(formatted_students)
    complete = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
    active = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
    warning = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
    reengage = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')
    total_progress = sum(s['progress']['value'] for s in formatted_students)
    avg_progress = round(total_progress / total, 1) if total > 0 else 0

    return {
        'totalStudents': total,
        'completeCount': complete,
        'activeCount': active,
        'warningCount': warning,
        'reengageCount': reengage,
        'averageProgress': avg_progress,
    }


def _fetch_dept_students(dept_id, token):
    """Fetch and annotate students for a single department. Returns (dept_meta, formatted_list)."""
    client = AbsorbAPIClient()
    client.set_token(token)

    raw, formatted = get_cached_students(dept_id, token)

    # Prefer the departmentName already present on the raw Absorb user records
    # (the /Departments/{id} endpoint is unreliable for depts the current token
    # has limited access to, but the OData /users filter returns departmentName
    # on each user). Falls back to the legacy endpoint only if no student carried
    # a name.
    dept_name = ''
    for u in raw or []:
        n = (u.get('departmentName') or '').strip()
        if n:
            dept_name = n
            break
    if not dept_name:
        dept_name = get_department_name(client, dept_id)

    # If the name is still empty or the literal 'Department'/'Unknown'
    # placeholder (get_department's 401 fallback), use the session-stored
    # name for the user's OWN primary department. That name was resolved at
    # login when the token was fresh, so it's reliable. Without this, the
    # primary dept shows as "Department" in the multi-dept filter + DEPT
    # column whenever the /Departments/{id} lookup 401s mid-load.
    if dept_name in ('', 'Department', 'Unknown'):
        try:
            session_user = g.user if hasattr(g, 'user') else None
            session_primary_id = (session_user or {}).get('departmentId') or ''
            session_primary_name = (session_user or {}).get('departmentName') or ''
            if (session_primary_name
                    and session_primary_name not in ('Department', 'Unknown')
                    and session_primary_id
                    and session_primary_id.lower() == (dept_id or '').lower()):
                dept_name = session_primary_name
        except Exception:
            pass

    # Inject departmentName into each student
    for s in formatted:
        s['departmentName'] = dept_name

    return {
        'id': dept_id,
        'name': dept_name,
        'studentCount': len(formatted),
        'status': 'ok',
    }, formatted


@dashboard_bp.route('/students/multi', methods=['GET'])
@login_required
def get_students_multi():
    """Get students from multiple departments, merged into one list."""
    try:
        extra_param = request.args.get('departments', '')
        extra_ids = [d.strip() for d in extra_param.split(',') if d.strip()] if extra_param else []

        # Validate GUIDs and cap at MAX_EXTRA_DEPTS
        valid_ids = []
        dept_meta = []
        for d in extra_ids[:MAX_EXTRA_DEPTS]:
            if GUID_RE.match(d):
                if d.lower() != (g.department_id or '').lower():
                    valid_ids.append(d)
            else:
                dept_meta.append({'id': d, 'name': None, 'studentCount': 0, 'status': 'error', 'error': 'Invalid GUID format'})

        # Always include user's own department
        all_dept_ids = [g.department_id] + valid_ids

        # Fetch all departments in parallel. The refresh path inside
        # _fetch_depts_collect is now guarded by an in-process threading
        # lock + cross-process fcntl file lock (see _refresh_user_absorb_token)
        # so concurrent re-auths from parallel requests can't clobber each
        # other's tokens. The previous warmup-probe approach was removed —
        # it was a second refresh source that caused the clobber race.
        all_formatted, fetched_meta = _fetch_depts_collect(all_dept_ids, g.absorb_token)
        dept_meta.extend(fetched_meta)

        expired_ids = _expired_dept_ids(dept_meta)
        if expired_ids and _refresh_user_absorb_token():
            print(f"[MULTI-DEPT] Retrying {len(expired_ids)} dept(s) after token refresh")
            for dept_id in expired_ids:
                invalidate_cache(dept_id)
            dept_meta = [m for m in dept_meta if m.get('id') not in expired_ids]
            retry_formatted, retry_meta = _fetch_depts_collect(expired_ids, g.absorb_token, sequential=True)
            all_formatted.extend(retry_formatted)
            dept_meta.extend(retry_meta)

        # Sort merged list
        all_formatted.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        return jsonify({
            'success': True,
            'students': all_formatted,
            'count': len(all_formatted),
            'summary': _compute_summary(all_formatted),
            'departments': dept_meta,
        })

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        import traceback
        print(f"[ERROR] Multi-dept fetch failed: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Failed to fetch students: {str(e)}'}), 500


@dashboard_bp.route('/sync', methods=['POST'])
@login_required
def sync_data():
    """
    Force sync/refresh data from Absorb LMS (clears cache).
    Accepts optional extraDepartments list in JSON body for multi-dept sync.
    """
    try:
        # Demo mode: static data, no sync needed
        if is_demo_dept(g.department_id):
            cached = get_cached_demo_students()
            formatted = [format_student_for_response(s) for s in cached]
            formatted.sort(key=lambda s: (s['status']['priority'], -s['progress']['value']))
            return jsonify({
                'success': True,
                'message': 'Demo mode - data is static',
                'summary': _compute_summary(formatted),
                'students': formatted,
                'departments': [{'id': DEMO_DEPT_ID, 'name': DEMO_DEPT_NAME,
                                 'studentCount': len(formatted), 'status': 'ok'}],
                'syncedAt': datetime.utcnow().isoformat()
            })

        data = request.get_json(silent=True) or {}
        extra_dept_ids = data.get('extraDepartments', [])

        # Build list of all dept IDs to sync
        all_dept_ids = [g.department_id]
        for d in extra_dept_ids[:MAX_EXTRA_DEPTS]:
            if isinstance(d, str) and GUID_RE.match(d) and d.lower() != (g.department_id or '').lower():
                all_dept_ids.append(d)

        dept_name = g.user.get('departmentName', 'Unknown')
        print(f"[SYNC] Starting sync for {len(all_dept_ids)} department(s): {dept_name} ({g.department_id})")

        # Invalidate student caches (not exam cache - that's separate data)
        for dept_id in all_dept_ids:
            invalidate_cache(dept_id)

        # Fetch all departments (parallel if multiple). Uses a helper so we
        # can cheaply retry only the departments that hit an Absorb 401
        # after transparently refreshing the user's token.
        all_formatted, dept_meta = _fetch_depts_collect(all_dept_ids, g.absorb_token)

        expired_ids = _expired_dept_ids(dept_meta)
        if expired_ids and _refresh_user_absorb_token():
            print(f"[SYNC] Retrying {len(expired_ids)} dept(s) after token refresh")
            # Invalidate any caches touched by the failed attempts
            for dept_id in expired_ids:
                invalidate_cache(dept_id)
            # Drop the expired error entries, keep successful ones
            dept_meta = [m for m in dept_meta if m.get('id') not in expired_ids]
            retry_formatted, retry_meta = _fetch_depts_collect(expired_ids, g.absorb_token, sequential=True)
            all_formatted.extend(retry_formatted)
            dept_meta.extend(retry_meta)

        # Sort
        all_formatted.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        print(f"[SYNC] Got {len(all_formatted)} students across {len(all_dept_ids)} departments")

        return jsonify({
            'success': True,
            'message': 'Data synced successfully',
            'summary': _compute_summary(all_formatted),
            'students': all_formatted,
            'departments': dept_meta,
            'syncedAt': g.user.get('loginTime')
        })

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Failed to sync data: {str(e)}'}), 500


@dashboard_bp.route('/export', methods=['GET'])
@login_required
def export_data():
    """
    Export student data as CSV.
    Accepts optional departments query param for multi-dept export.
    """
    from flask import Response
    import csv
    from io import StringIO

    try:
        extra_param = request.args.get('departments', '')
        extra_ids = [d.strip() for d in extra_param.split(',') if d.strip() and GUID_RE.match(d.strip())] if extra_param else []
        multi_dept = len(extra_ids) > 0

        # Build dept list
        all_dept_ids = [g.department_id]
        for d in extra_ids[:MAX_EXTRA_DEPTS]:
            if d.lower() != (g.department_id or '').lower():
                all_dept_ids.append(d)

        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Gather all students
        all_students = []
        for dept_id in all_dept_ids:
            raw, _ = get_cached_students(dept_id, g.absorb_token)
            dept_name = get_department_name(client, dept_id) if multi_dept else ''
            for student in raw:
                student['_dept_name'] = dept_name
            all_students.extend(raw)

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        headers = ['First Name', 'Last Name', 'Email', 'Status', 'Last Login', 'Course', 'Progress (%)', 'Time Spent (minutes)']
        if multi_dept:
            headers.insert(0, 'Department')
        writer.writerow(headers)

        for student in all_students:
            status = get_status_from_last_login(student.get('lastLoginDate'))
            row = [
                student.get('firstName', ''),
                student.get('lastName', ''),
                student.get('emailAddress', ''),
                status['status'],
                student.get('lastLoginDate', 'Never'),
                student.get('courseName', 'No Course'),
                round(student.get('progress', 0), 1),
                student.get('timeSpent', 0)
            ]
            if multi_dept:
                row.insert(0, student.get('_dept_name', ''))
            writer.writerow(row)

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=students_export_{g.department_id[:8]}.csv'
            }
        )

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to export data'}), 500


# ── User Department Preferences ──────────────────────────────────────

@dashboard_bp.route('/dept-prefs', methods=['GET'])
@login_required
def get_dept_prefs():
    """Get the logged-in user's saved extra departments."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    if not email:
        return jsonify({'success': False, 'error': 'No user email in session'}), 401
    dept_ids = get_user_dept_prefs(email)
    return jsonify({'success': True, 'departmentIds': dept_ids})


@dashboard_bp.route('/dept-prefs', methods=['POST'])
@login_required
def save_dept_prefs():
    """Save the logged-in user's extra departments."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    if not email:
        return jsonify({'success': False, 'error': 'No user email in session'}), 401
    data = request.get_json() or {}
    dept_ids = data.get('departmentIds', [])
    valid = [d for d in dept_ids[:MAX_EXTRA_DEPTS] if isinstance(d, str) and GUID_RE.match(d)]
    save_user_dept_prefs(email, valid)
    return jsonify({'success': True, 'departmentIds': valid})


# ── User Hidden Students ─────────────────────────────────────────────

@dashboard_bp.route('/hidden-students', methods=['GET'])
@login_required
def get_hidden_students():
    """Get the logged-in user's hidden student emails."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    if not email:
        return jsonify({'success': False, 'error': 'No user email in session'}), 401
    hidden = get_user_hidden_students(email)
    return jsonify({'success': True, 'hiddenEmails': hidden})


@dashboard_bp.route('/hidden-students', methods=['POST'])
@login_required
def save_hidden_students():
    """Save the logged-in user's hidden student emails."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    if not email:
        return jsonify({'success': False, 'error': 'No user email in session'}), 401
    data = request.get_json() or {}
    hidden = data.get('hiddenEmails', [])
    valid = [e for e in hidden[:200] if isinstance(e, str) and e.strip()]
    save_user_hidden_students(email, valid)
    return jsonify({'success': True, 'hiddenEmails': valid})


# ── User GHL Settings ────────────────────────────────────────────────

@dashboard_bp.route('/ghl-settings', methods=['GET'])
@login_required
def get_ghl_settings():
    """Get the logged-in user's GHL integration settings (token masked)."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    settings = get_user_ghl_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/ghl-settings', methods=['POST'])
@login_required
def save_ghl_settings():
    """Save GHL integration settings for the logged-in user."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    data = request.get_json() or {}

    # Mutual exclusivity: disable Bitrix and User Sheet if enabling GHL
    if data.get('enabled'):
        save_user_bitrix_settings(email, enabled=False)
        save_user_sheet_settings(email, enabled=False)
        from bitrix_api import invalidate_bitrix_cache
        from google_sheets import invalidate_user_sheet_cache
        invalidate_bitrix_cache(email)
        invalidate_user_sheet_cache(email)

    save_user_ghl_settings(
        email,
        enabled=data.get('enabled'),
        ghl_token=data.get('ghl_token'),
        location_id=data.get('location_id'),
        calendar_id=data.get('calendar_id'),
    )

    # Clear GHL cache so next exam fetch uses fresh data
    from ghl_api import invalidate_ghl_cache
    invalidate_ghl_cache(email)

    settings = get_user_ghl_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/ghl-calendars', methods=['GET'])
@login_required
def get_ghl_calendars():
    """Fetch available GHL calendars for the user's configured token + location."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    token = request.args.get('token', '').strip()
    location_id = request.args.get('location_id', '').strip()

    if not token or not location_id:
        return jsonify({'success': False, 'error': 'Token and Location ID are required'}), 400

    try:
        from ghl_api import fetch_ghl_calendars
        calendars = fetch_ghl_calendars(token, location_id)
        return jsonify({'success': True, 'calendars': calendars})
    except _requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 500
        if status == 401:
            return jsonify({'success': False, 'error': 'Invalid GHL token'}), 401
        return jsonify({'success': False, 'error': f'GHL API error ({status})'}), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── User Bitrix24 Settings ──────────────────────────────────────────

@dashboard_bp.route('/bitrix-settings', methods=['GET'])
@login_required
def get_bitrix_settings():
    """Get the logged-in user's Bitrix24 integration settings (webhook masked)."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    settings = get_user_bitrix_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/bitrix-settings', methods=['POST'])
@login_required
def save_bitrix_settings():
    """Save Bitrix24 integration settings for the logged-in user."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    data = request.get_json() or {}

    # Mutual exclusivity: disable GHL and User Sheet if enabling Bitrix
    if data.get('enabled'):
        save_user_ghl_settings(email, enabled=False)
        save_user_sheet_settings(email, enabled=False)
        from ghl_api import invalidate_ghl_cache
        from google_sheets import invalidate_user_sheet_cache
        invalidate_ghl_cache(email)
        invalidate_user_sheet_cache(email)

    save_user_bitrix_settings(
        email,
        enabled=data.get('enabled'),
        webhook_url=data.get('webhook_url'),
    )

    # Clear Bitrix cache so next exam fetch uses fresh data
    from bitrix_api import invalidate_bitrix_cache
    invalidate_bitrix_cache(email)

    settings = get_user_bitrix_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/bitrix-validate', methods=['GET'])
@login_required
def validate_bitrix_webhook():
    """Validate a Bitrix24 webhook URL by testing the connection."""
    webhook_url = request.args.get('webhook_url', '').strip()

    if not webhook_url:
        return jsonify({'success': False, 'error': 'Webhook URL is required'}), 400

    from bitrix_api import validate_webhook
    result = validate_webhook(webhook_url)

    if result.get('valid'):
        return jsonify({'success': True, **result})
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Validation failed')}), 400


# ── User Google Sheet Settings ──────────────────────────────────────

@dashboard_bp.route('/sheet-settings', methods=['GET'])
@login_required
def get_sheet_settings():
    """Get the logged-in user's Google Sheet settings."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    settings = get_user_sheet_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/sheet-settings', methods=['POST'])
@login_required
def save_sheet_settings():
    """Save Google Sheet settings for the logged-in user."""
    email = (g.user.get('email') or g.user.get('emailAddress') or '').lower().strip()
    data = request.get_json() or {}

    # Mutual exclusivity: disable GHL and Bitrix if enabling User Sheet
    if data.get('enabled'):
        save_user_ghl_settings(email, enabled=False)
        save_user_bitrix_settings(email, enabled=False)
        from ghl_api import invalidate_ghl_cache
        from bitrix_api import invalidate_bitrix_cache
        invalidate_ghl_cache(email)
        invalidate_bitrix_cache(email)

    # Parse sheet URL to extract ID
    sheet_url = data.get('sheet_url', '').strip()
    sheet_id = None
    if sheet_url:
        from google_sheets import parse_sheet_id
        sheet_id = parse_sheet_id(sheet_url)

    print(f"[SHEET SETTINGS] Saving for {email}: enabled={data.get('enabled')}, url={sheet_url[:50] if sheet_url else 'EMPTY'}, parsed_id={sheet_id}")

    save_user_sheet_settings(
        email,
        enabled=data.get('enabled'),
        sheet_url=sheet_url if sheet_url else None,
        sheet_id=sheet_id,
    )

    from google_sheets import invalidate_user_sheet_cache
    invalidate_user_sheet_cache(email)

    settings = get_user_sheet_settings_masked(email)
    return jsonify({'success': True, **settings})


@dashboard_bp.route('/sheet-validate', methods=['GET'])
@login_required
def validate_sheet():
    """Validate a Google Sheet URL by testing fetch and checking columns."""
    sheet_url = request.args.get('sheet_url', '').strip()
    if not sheet_url:
        return jsonify({'success': False, 'error': 'Sheet URL is required'}), 400

    from google_sheets import parse_sheet_id, validate_user_sheet
    sheet_id = parse_sheet_id(sheet_url)
    if not sheet_id:
        return jsonify({'success': False, 'error': 'Could not parse a valid Google Sheet ID from that URL'}), 400

    result = validate_user_sheet(sheet_id)
    if result.get('valid'):
        return jsonify({'success': True, **result})
    return jsonify({'success': False, 'error': result.get('error', 'Validation failed')}), 400
