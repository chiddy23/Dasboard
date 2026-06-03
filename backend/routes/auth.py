"""Authentication routes for JustInsurance Student Dashboard."""

from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import rate_limit, login_required, get_current_user
from utils import validate_login_input, sanitize_string
from utils.credential_store import encrypt_password
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@rate_limit()
def login():
    """
    Authenticate user with Absorb LMS credentials.

    Expected JSON body:
    {
        "username": "user@email.com",
        "password": "their_password",
        "departmentId": "GUID-FORMAT-ID"
    }

    Returns:
        JSON response with session token and user info
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400

        # Extract and sanitize inputs
        username = sanitize_string(data.get('username', ''))
        password = data.get('password', '')  # Don't sanitize password
        department_id = sanitize_string(data.get('departmentId', ''))

        # Validate inputs
        is_valid, error = validate_login_input(username, password, department_id)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error
            }), 400

        # Initialize Absorb API client
        client = AbsorbAPIClient()

        # Step 1: Authenticate user with Absorb API
        try:
            auth_result = client.authenticate_user(username, password)
        except AbsorbAPIError as e:
            if e.status_code == 401:
                return jsonify({
                    'success': False,
                    'error': 'Invalid username or password'
                }), 401
            raise

        # Check allowlist before proceeding
        from snapshot_db import is_user_allowed
        if not is_user_allowed(username):
            return jsonify({
                'success': False,
                'error': 'Account not authorized. Please contact your administrator for access.'
            }), 403

        # Set the token for subsequent API calls
        client.set_token(auth_result['token'])

        # Step 2: Get department info (don't verify users at login - too slow)
        print(f"[LOGIN] Getting department info: {department_id}")
        try:
            department = client.get_department(department_id)
        except AbsorbAPIError:
            department = {'id': department_id, 'name': 'Department'}

        # Get department name - handle both v1 (Name) and v2 (name) formats
        dept_name = department.get('Name') or department.get('name', 'Department')
        print(f"[LOGIN] Department: {dept_name}")

        # Step 4: Create session
        token_expires_at = datetime.utcnow() + timedelta(hours=4)

        # Encrypt the user's password into their session so sync/multi
        # endpoints can transparently re-auth with Absorb when the ~4-hour
        # token TTL hits. The blob is Fernet-encrypted with SECRET_KEY and
        # lives only in the filesystem session file (wiped on logout, on
        # session expiry, and on every Render redeploy). The refreshed
        # token belongs to the user themselves — tenant isolation preserved.
        enc_pwd = encrypt_password(password, Config.SECRET_KEY)

        session['user'] = {
            'id': username,
            'username': username,
            'email': username,
            'firstName': username.split('@')[0].title(),
            'lastName': '',
            'departmentId': department_id,
            'departmentName': dept_name,
            'token': auth_result['token'],
            'tokenExpiresAt': token_expires_at.isoformat(),
            'loginTime': datetime.utcnow().isoformat(),
            # Encrypted password blob — decrypted only inside
            # dashboard._refresh_user_absorb_token when a 401 is hit.
            'absorbPasswordEnc': enc_pwd,
        }

        session.permanent = True

        # Sync the fresh token into the process-global store used by the
        # cross-request CAS in _refresh_user_absorb_token. Login just minted a
        # new token (which revoked any previous one), so without this the global
        # still holds the OLD/revoked token — and the CAS would "reuse" that
        # stale token on the first post-login 401, poisoning the session and
        # collapsing the first dashboard load. Keep global == the live token.
        try:
            from routes.dashboard import _latest_user_tokens
            _latest_user_tokens[(username or '').lower().strip()] = auth_result['token']
        except Exception:
            pass

        # Register this user as actively logged in. Any zombie /students or
        # /summary retry loop still alive on the server from a prior session
        # will check this set before re-Auth-ing; a logged-out user is a
        # zombie and won't /Authenticate, so it can't revoke this fresh
        # login's chad token. See _refresh_user_absorb_token guard.
        try:
            from routes.dashboard import _active_user_logins, _active_logins_lock
            with _active_logins_lock:
                _active_user_logins.add((username or '').lower().strip())
        except Exception:
            pass

        return jsonify({
            'success': True,
            'user': {
                'id': username,
                'name': username.split('@')[0].title(),
                'email': username,
                'firstName': username.split('@')[0].title(),
                'lastName': ''
            },
            'department': {
                'id': department_id,
                'name': dept_name
            },
            'expiresAt': token_expires_at.isoformat()
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Log out the current user and clear session.

    Returns:
        JSON response confirming logout
    """
    # Capture username BEFORE clearing the session so we can deregister this
    # user from the active-logins set. Any in-flight /students or /summary
    # request from this session will keep running on the server (Flask doesn't
    # abort on browser disconnect) and will hit the retry loop. Removing the
    # user here makes _refresh_user_absorb_token bail instead of minting a
    # zombie /Authenticate that would revoke the user's NEXT login token.
    user_data = session.get('user') or {}
    uname = (user_data.get('username') or user_data.get('email') or '').lower().strip()
    session.clear()
    if uname:
        try:
            from routes.dashboard import _active_user_logins, _active_logins_lock
            with _active_logins_lock:
                _active_user_logins.discard(uname)
        except Exception:
            pass
        # Clear the refresh-debounce stamp so a fresh login isn't held back by
        # a stale prior session's mint time. The next login mints a fresh token
        # which Absorb will revoke any prior with; debouncing against a token
        # we don't even have anymore would just defer the new mint pointlessly.
        try:
            from routes.dashboard import _last_mint_at
            _last_mint_at.pop(uname, None)
        except Exception:
            pass
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })


@auth_bp.route('/session', methods=['GET'])
@login_required
def get_session():
    """
    Get current session information.

    Returns:
        JSON response with user and department info
    """
    user = get_current_user()

    if not user:
        return jsonify({
            'success': False,
            'error': 'Not authenticated'
        }), 401

    return jsonify({
        'success': True,
        'user': {
            'id': user.get('id'),
            'name': f"{user.get('firstName', '')} {user.get('lastName', '')}".strip(),
            'email': user.get('email'),
            'firstName': user.get('firstName', ''),
            'lastName': user.get('lastName', '')
        },
        'department': {
            'id': user.get('departmentId'),
            'name': user.get('departmentName', 'Unknown')
        },
        'expiresAt': user.get('tokenExpiresAt')
    })


@auth_bp.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    """Lightweight keepalive called by the frontend every 3 minutes.

    DO NOT make Absorb calls from this route. Per memory rules
    (feedback_dashboard_absorb_auth_rules), a working heartbeat that pings
    Absorb becomes a 3rd /Authenticate source that races sync_scheduler +
    user routes → single-session-per-account token war. The previous
    implementation accidentally enforced the no-Absorb-call invariant via
    a NameError on `g.absorb_token` (g not imported), which Flask logged
    as a full stack trace on EVERY heartbeat — ~22 lines per fire, every
    3 min, drowning the 100-line Render free-tier log buffer and blocking
    diagnosis of every actual bug (see 2026-06-03 log: 88 of 100 lines
    were heartbeat tracebacks).

    Fix: keep the route alive (frontend expects 200) but make it truly
    a no-op. No Absorb call, no log spam. The session's tokenExpiresAt
    is read straight from the session — no Bearer needed.
    """
    user = get_current_user()
    return jsonify({
        'success': True,
        'status': 'alive',
        'expiresAt': user.get('tokenExpiresAt') if user else None,
    })
