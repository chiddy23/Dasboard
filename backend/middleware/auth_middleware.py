"""Authentication middleware for protected routes."""

from functools import wraps
from flask import session, jsonify, request, g
from datetime import datetime


def login_required(f):
    """
    Decorator to require authentication for a route.

    Checks for valid session with Absorb token and department ID.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        import sys

        # Check if user is logged in
        if 'user' not in session:
            print(f"[AUTH FAIL] No user in session. Path: {request.path}", file=sys.stderr, flush=True)
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'code': 'AUTH_REQUIRED'
            }), 401

        # Check if session has required data
        user_data = session.get('user', {})
        if not user_data.get('token') or not user_data.get('departmentId'):
            print(f"[AUTH FAIL] Missing token/dept. Path: {request.path}", file=sys.stderr, flush=True)
            return jsonify({
                'success': False,
                'error': 'Invalid session',
                'code': 'INVALID_SESSION'
            }), 401

        # Check token expiration
        expires_at = user_data.get('tokenExpiresAt')
        if expires_at:
            try:
                if isinstance(expires_at, str):
                    expiry = datetime.fromisoformat(expires_at)
                else:
                    expiry = expires_at

                if datetime.utcnow() > expiry:
                    # Clear expired session
                    session.clear()
                    return jsonify({
                        'success': False,
                        'error': 'Session expired. Please log in again.',
                        'code': 'SESSION_EXPIRED'
                    }), 401
            except (ValueError, TypeError):
                pass

        # Store user data in g for access in route
        g.user = user_data
        g.department_id = user_data.get('departmentId')
        g.absorb_token = user_data.get('token')

        return f(*args, **kwargs)

    return decorated_function


def get_current_user():
    """
    Get the current authenticated user from the session.

    Returns:
        User dictionary or None if not authenticated
    """
    return session.get('user')


def get_current_department_id():
    """
    Get the current department ID from the session.

    Returns:
        Department ID string or None
    """
    user = get_current_user()
    return user.get('departmentId') if user else None


def get_absorb_token():
    """
    Get the Absorb API token from the session.

    Returns:
        Token string or None
    """
    user = get_current_user()
    return user.get('token') if user else None
