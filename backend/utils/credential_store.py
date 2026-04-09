"""Session-scoped credential encryption helpers.

Used to stash the user's Absorb password inside their Flask session so that
on-demand sync endpoints can transparently re-authenticate when the user's
Absorb token hits its ~4-hour TTL. The refreshed token is the user's OWN
(not an admin/impersonation) so tenant isolation is preserved.

Design notes:
- Fernet (symmetric AES-128-CBC + HMAC) from the cryptography library.
- Key is derived from the Flask SECRET_KEY via SHA-256 so the same deploy
  can always decrypt what it encrypted. SECRET_KEY is set on Render as an
  env var and already required for Flask-Session itself.
- Stored encrypted blob is a str (base64) so it serializes cleanly into
  Flask-Session's session file.
- Never log or print the plaintext password under any circumstance.
- Session file lives on Render's filesystem, is scoped per-user via the
  session cookie, and is wiped on logout, session expiry, and on every
  Render redeploy — so password lifetime on disk is bounded.
"""

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(secret_key: str) -> bytes:
    """Derive a stable 32-byte Fernet key from the Flask SECRET_KEY."""
    if not secret_key:
        raise ValueError('SECRET_KEY must be set to use credential store')
    digest = hashlib.sha256(secret_key.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_password(plaintext: str, secret_key: str) -> Optional[str]:
    """Encrypt a password for session storage. Returns None on failure
    so callers can fall back to the current behavior (no refresh capable)."""
    if not plaintext or not secret_key:
        return None
    try:
        fernet = Fernet(_derive_fernet_key(secret_key))
        token = fernet.encrypt(plaintext.encode('utf-8'))
        return token.decode('ascii')
    except Exception:
        # Intentionally no details in the error message to avoid leaking
        # any partial state of the password into logs.
        print('[CRED STORE] encrypt_password failed')
        return None


def decrypt_password(blob: str, secret_key: str) -> Optional[str]:
    """Decrypt a previously-stored password blob. Returns None if the blob
    is missing, corrupted, or was encrypted under a different SECRET_KEY
    (e.g. after a key rotation). Callers should treat None as "no refresh
    possible — user must log in again"."""
    if not blob or not secret_key:
        return None
    try:
        fernet = Fernet(_derive_fernet_key(secret_key))
        return fernet.decrypt(blob.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError, Exception):
        print('[CRED STORE] decrypt_password failed')
        return None
