"""Formatting utilities for dates, times, and data."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any


def parse_absorb_date(date_string: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string from Absorb API.

    Args:
        date_string: ISO format date string from Absorb

    Returns:
        datetime object or None if invalid
    """
    if not date_string:
        return None

    try:
        # Handle various ISO formats
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'

        # Try parsing with timezone
        try:
            return datetime.fromisoformat(date_string)
        except ValueError:
            # Try without timezone
            return datetime.fromisoformat(date_string.replace('+00:00', ''))
    except (ValueError, AttributeError):
        return None


def format_relative_time(dt: Optional[datetime]) -> str:
    """
    Format a datetime as relative time (e.g., "2 hours ago").

    Args:
        dt: datetime object

    Returns:
        Formatted relative time string
    """
    if not dt:
        return "Never"

    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()

    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 0:
        return "Just now"

    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}d ago"
    else:
        return dt.strftime("%b %d, %Y")


def format_datetime(dt: Optional[datetime], format_str: str = "%b %d, %Y %I:%M %p") -> str:
    """
    Format a datetime for display.

    Args:
        dt: datetime object
        format_str: strftime format string

    Returns:
        Formatted date string
    """
    if not dt:
        return "N/A"

    return dt.strftime(format_str)


def get_status_from_last_login(last_login: Optional[str]) -> Dict[str, Any]:
    """
    Determine student status based on last login date.

    Thresholds:
        <= 24h: ACTIVE (green)
        1-3 days: WARNING (orange)
        3-7 days: RE-ENGAGE (red)
        7+ days: ABANDONED (dark gray)
        No login: ABANDONED
    """
    if not last_login:
        return {
            'status': 'ABANDONED',
            'class': 'gray',
            'emoji': '⚫',
            'priority': 4
        }

    last_login_dt = parse_absorb_date(last_login)

    if not last_login_dt:
        return {
            'status': 'ABANDONED',
            'class': 'gray',
            'emoji': '⚫',
            'priority': 4
        }

    now = datetime.now(timezone.utc) if last_login_dt.tzinfo else datetime.now()
    days_diff = (now - last_login_dt).total_seconds() / 86400

    if days_diff <= 1:
        return {
            'status': 'ACTIVE',
            'class': 'green',
            'emoji': '🟢',
            'priority': 1
        }
    elif days_diff <= 3:
        return {
            'status': 'WARNING',
            'class': 'orange',
            'emoji': '🟡',
            'priority': 2
        }
    elif days_diff <= 7:
        return {
            'status': 'RE-ENGAGE',
            'class': 'red',
            'emoji': '🔴',
            'priority': 3
        }
    else:
        return {
            'status': 'ABANDONED',
            'class': 'gray',
            'emoji': '⚫',
            'priority': 4
        }


def parse_time_spent_to_minutes(time_value) -> int:
    """
    Parse time spent value to minutes.
    Absorb API returns time as .NET TimeSpan: [d.]HH:MM:SS[.fffffff]

    Examples:
        '01:26:11.9878697'     -> 86 min (1h 26m)
        '1.13:02:39.9878697'   -> 2222 min (1d 13h 2m)
        '37:02:39'             -> 2222 min (37h 2m)

    Args:
        time_value: Time value (can be [d.]HH:MM:SS string, int minutes, or None)

    Returns:
        Time in minutes as integer
    """
    if not time_value:
        return 0

    # If it's already a number, assume it's minutes
    if isinstance(time_value, (int, float)):
        return int(time_value)

    # If it's a string in .NET TimeSpan format
    if isinstance(time_value, str):
        try:
            parts = time_value.split(':')
            if len(parts) >= 2:
                days = 0
                first = parts[0]
                # Check for days prefix: "1.13" in "1.13:02:39.9878697"
                if '.' in first:
                    day_hour = first.split('.')
                    days = int(day_hour[0])
                    hours = int(day_hour[1])
                else:
                    hours = int(first)
                mins = int(parts[1])
                return days * 1440 + hours * 60 + mins
            else:
                # Try parsing as a number
                return int(float(time_value))
        except (ValueError, TypeError):
            return 0

    return 0


def format_time_spent(time_value) -> str:
    """
    Format time spent to human-readable format.

    Args:
        time_value: Time value (HH:MM:SS string or minutes as int/float)

    Returns:
        Formatted time string (e.g., "2h 30m")
    """
    minutes = parse_time_spent_to_minutes(time_value)

    if minutes <= 0:
        return "0m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours > 0:
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"
    else:
        return f"{remaining_minutes}m"


def format_progress(progress) -> Dict[str, Any]:
    """
    Format progress percentage with color coding.

    Args:
        progress: Progress percentage (0-100), can be int, float, or string

    Returns:
        Dictionary with formatted progress data
    """
    # Convert to float, handling strings and None
    try:
        progress = float(progress) if progress else 0
    except (ValueError, TypeError):
        progress = 0

    progress = max(0, min(100, progress))

    if progress >= 75:
        color_class = 'high'
        color = '#22c55e'  # Green
    elif progress >= 40:
        color_class = 'med'
        color = '#f97316'  # Orange
    else:
        color_class = 'low'
        color = '#ef4444'  # Red

    return {
        'value': round(progress, 1),
        'display': f"{round(progress)}%",
        'colorClass': color_class,
        'color': color
    }


def _is_enrollment_expired(student: Dict[str, Any]) -> bool:
    """Check if the student's primary enrollment is expired."""
    # Check enrollment status (4 = Expired in some Absorb versions)
    enrollment_status = student.get('enrollmentStatus', 0)
    if enrollment_status == 4:
        return True

    # Check expiry date fields on the primary enrollment
    primary = student.get('primaryEnrollment') or {}
    for key in ('dateExpired', 'DateExpired', 'expiryDate', 'ExpiryDate',
                'dateExpiry', 'DateExpiry', 'expiredDate', 'ExpiredDate'):
        expiry_str = primary.get(key)
        if expiry_str:
            expiry_dt = parse_absorb_date(expiry_str)
            if expiry_dt:
                now = datetime.now(timezone.utc) if expiry_dt.tzinfo else datetime.now()
                if expiry_dt < now:
                    return True
    return False


def format_student_for_response(student: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a student record for API response.

    Status priority:
        1. COMPLETE (100% progress) - skip all warnings
        2. COURSE EXPIRED - enrollment expired
        3. ACTIVE / WARNING / RE-ENGAGE / ABANDONED - based on login recency
    """
    last_login = student.get('lastLoginDate')
    progress_info = format_progress(student.get('progress', 0))

    # If student completed the course (100% progress), mark as COMPLETE
    if progress_info['value'] >= 100:
        status_info = {
            'status': 'COMPLETE',
            'class': 'blue',
            'emoji': '\u2705',
            'priority': 0
        }
    elif _is_enrollment_expired(student):
        status_info = {
            'status': 'COURSE EXPIRED',
            'class': 'expired',
            'emoji': '⏰',
            'priority': 5
        }
    else:
        status_info = get_status_from_last_login(last_login)

    return {
        'id': student.get('id'),
        'firstName': student.get('firstName', ''),
        'lastName': student.get('lastName', ''),
        'fullName': f"{student.get('firstName', '')} {student.get('lastName', '')}".strip(),
        'email': student.get('emailAddress', ''),
        'phone': student.get('phone') or student.get('Phone') or '',
        'username': student.get('username', ''),
        'lastLogin': {
            'raw': last_login,
            'formatted': format_datetime(parse_absorb_date(last_login)),
            'relative': format_relative_time(parse_absorb_date(last_login))
        },
        'status': status_info,
        'courseName': student.get('courseName', 'No Course'),
        'progress': progress_info,
        'timeSpent': {
            'minutes': student.get('timeSpent', 0),
            'formatted': format_time_spent(student.get('timeSpent', 0))
        },
        'examPrepTime': {
            'minutes': student.get('examPrepTime', 0),
            'formatted': format_time_spent(student.get('examPrepTime', 0))
        },
        'enrollmentStatus': student.get('enrollmentStatus', 0),
        'enrollmentStatusText': get_enrollment_status_text(student.get('enrollmentStatus', 0)),
        'departmentId': student.get('departmentId', '')
    }


def get_enrollment_status_text(status: int) -> str:
    """
    Get human-readable enrollment status.

    Args:
        status: Enrollment status code from Absorb API

    Returns:
        Status text
    """
    status_map = {
        0: 'Not Started',
        1: 'In Progress',
        2: 'Complete',
        3: 'Complete',  # Absorb API uses 3 for completed
        4: 'Expired'
    }
    return status_map.get(status, 'Unknown')
