"""Input validation utilities."""

import re
from typing import Tuple, Optional

# UUID/GUID pattern for department IDs
UUID_PATTERN = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)

# Email pattern
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_department_id(department_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a department ID (GUID format).

    Args:
        department_id: The department ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not department_id:
        return False, "Department ID is required"

    if not isinstance(department_id, str):
        return False, "Department ID must be a string"

    department_id = department_id.strip()

    if not UUID_PATTERN.match(department_id):
        return False, "Invalid Department ID format. Expected GUID format (e.g., 63CADAFD-668F-4738-A273-B9FD02A79BF5)"

    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an email address.

    Args:
        email: The email to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    if not isinstance(email, str):
        return False, "Email must be a string"

    email = email.strip()

    if len(email) > 254:
        return False, "Email is too long"

    if not EMAIL_PATTERN.match(email):
        return False, "Invalid email format"

    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a username (can be email or username).

    Args:
        username: The username to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"

    if not isinstance(username, str):
        return False, "Username must be a string"

    username = username.strip()

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 254:
        return False, "Username is too long"

    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a password.

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if not isinstance(password, str):
        return False, "Password must be a string"

    if len(password) < 1:
        return False, "Password is required"

    return True, None


def validate_login_input(username: str, password: str, department_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate all login inputs.

    Args:
        username: The username/email
        password: The password
        department_id: The department ID

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_username(username)
    if not is_valid:
        return False, error

    is_valid, error = validate_password(password)
    if not is_valid:
        return False, error

    is_valid, error = validate_department_id(department_id)
    if not is_valid:
        return False, error

    return True, None


def sanitize_string(value: str) -> str:
    """
    Sanitize a string input.

    Args:
        value: The string to sanitize

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Strip whitespace
    value = value.strip()

    # Remove null bytes
    value = value.replace('\x00', '')

    return value
