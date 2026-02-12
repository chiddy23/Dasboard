"""Utility modules for JustInsurance Student Dashboard."""

from .validators import (
    validate_department_id,
    validate_email,
    validate_username,
    validate_password,
    validate_login_input,
    sanitize_string
)

from .gap_metrics import calculate_gap_metrics

from .formatters import (
    parse_absorb_date,
    format_relative_time,
    format_datetime,
    get_status_from_last_login,
    format_time_spent,
    format_progress,
    format_student_for_response,
    get_enrollment_status_text
)

__all__ = [
    'calculate_gap_metrics',
    'validate_department_id',
    'validate_email',
    'validate_username',
    'validate_password',
    'validate_login_input',
    'sanitize_string',
    'parse_absorb_date',
    'format_relative_time',
    'format_datetime',
    'get_status_from_last_login',
    'format_time_spent',
    'format_progress',
    'format_student_for_response',
    'get_enrollment_status_text'
]
