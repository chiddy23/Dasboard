"""Student detail routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils import (
    format_student_for_response,
    format_progress,
    format_time_spent,
    get_enrollment_status_text,
    parse_absorb_date,
    format_datetime,
    format_relative_time
)
from utils.formatters import parse_time_spent_to_minutes


def is_prelicensing_course(name):
    """Check if course is pre-licensing related."""
    if not name:
        return False
    lower = name.lower()
    return ('pre-licens' in lower or 'prelicens' in lower or 'pre licens' in lower)


def is_chapter_or_module(name):
    """Check if course is a chapter/module."""
    if not name:
        return False
    lower = name.lower()
    return ('module' in lower or 'chapter' in lower or 'lesson' in lower or 'unit' in lower)


def calculate_prelicensing_totals(enrollments):
    """
    Calculate total time spent and average progress across all pre-licensing courses.
    Returns: (total_time_minutes, average_progress, course_name, primary_status)
    """
    prelicensing_enrollments = []
    main_course_name = "Pre-License Course"
    primary_status = 0

    for e in enrollments:
        name = e.get('courseName') or ''
        if is_prelicensing_course(name) or is_chapter_or_module(name):
            prelicensing_enrollments.append(e)
            # Track main course name (not a module/chapter)
            if is_prelicensing_course(name) and not is_chapter_or_module(name):
                main_course_name = name
                primary_status = e.get('status', 0)

    if not prelicensing_enrollments:
        # Fall back to first enrollment
        if enrollments:
            e = enrollments[0]
            time_val = parse_time_spent_to_minutes(e.get('timeSpent', 0))
            progress = e.get('progress', 0)
            return time_val, progress, e.get('courseName', 'No Course'), e.get('status', 0)
        return 0, 0, 'No Course', 0

    # Calculate totals
    total_time = 0
    progress_values = []

    for e in prelicensing_enrollments:
        time_val = parse_time_spent_to_minutes(e.get('timeSpent', 0))
        total_time += time_val

        progress = e.get('progress', 0)
        if isinstance(progress, (int, float)):
            progress_values.append(progress)

    avg_progress = sum(progress_values) / len(progress_values) if progress_values else 0

    return total_time, avg_progress, main_course_name, primary_status

students_bp = Blueprint('students', __name__)


@students_bp.route('/<student_id>', methods=['GET'])
@login_required
def get_student_details(student_id):
    """
    Get detailed information for a specific student.

    Args:
        student_id: The student's GUID

    Returns:
        JSON response with detailed student information
    """
    try:
        # Initialize API client with user's token
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Get users in department to verify student belongs to this department
        users = client.get_users_by_department(g.department_id)

        # Find the student (case-insensitive comparison)
        student = None
        student_id_lower = student_id.lower()
        for user in users:
            user_id = (user.get('id') or user.get('Id') or '').lower()
            if user_id == student_id_lower:
                student = user
                break

        if not student:
            return jsonify({
                'success': False,
                'error': 'Student not found in your department'
            }), 404

        # Get all enrollments for this student
        enrollments = client.get_user_enrollments(student_id)

        # Format enrollments (Absorb API field names)
        formatted_enrollments = []
        for enrollment in enrollments:
            # Extract values with correct Absorb API field names
            progress_val = enrollment.get('progress', 0)
            time_spent_val = enrollment.get('timeSpent') or '0'  # HH:MM:SS string
            status_val = enrollment.get('status', 0)
            course_name = enrollment.get('courseName') or 'Unknown Course'
            enrollment_id = enrollment.get('id')
            course_id = enrollment.get('courseId')

            # Date fields from Absorb API
            date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
            date_completed = enrollment.get('dateCompleted')
            # accessDate is often None, fallback to dateEdited or dateStarted
            date_last_accessed = (enrollment.get('accessDate') or
                                  enrollment.get('dateEdited') or
                                  enrollment.get('dateStarted'))

            progress_info = format_progress(progress_val)
            formatted_enrollments.append({
                'id': enrollment_id,
                'courseId': course_id,
                'courseName': course_name,
                'progress': progress_info,
                'timeSpent': {
                    'minutes': time_spent_val,
                    'formatted': format_time_spent(time_spent_val)
                },
                'status': status_val,
                'statusText': get_enrollment_status_text(status_val),
                'enrolledDate': format_datetime(parse_absorb_date(date_enrolled)),
                'completedDate': format_datetime(parse_absorb_date(date_completed)),
                'lastAccessed': {
                    'formatted': format_datetime(parse_absorb_date(date_last_accessed)),
                    'relative': format_relative_time(parse_absorb_date(date_last_accessed))
                }
            })

        # Sort enrollments: in progress first, then by progress
        formatted_enrollments.sort(
            key=lambda e: (
                0 if e['status'] == 1 else 1,  # In progress first
                -e['progress']['value']  # Higher progress first
            )
        )

        # Calculate totals across all pre-licensing courses
        total_time, avg_progress, course_name, primary_status = calculate_prelicensing_totals(enrollments)

        # Add enrollment data to student with calculated totals
        student['enrollments'] = enrollments
        student['progress'] = avg_progress
        student['timeSpent'] = total_time  # Already in minutes
        student['courseName'] = course_name
        student['enrollmentStatus'] = primary_status

        # Format basic student info
        formatted_student = format_student_for_response(student)

        # Add detailed enrollment data
        formatted_student['enrollments'] = formatted_enrollments
        formatted_student['totalEnrollments'] = len(enrollments)
        # Count completed (status 2 or 3 - Absorb uses 3 for completed)
        formatted_student['completedEnrollments'] = sum(1 for e in enrollments if e.get('status') in [2, 3])

        return jsonify({
            'success': True,
            'student': formatted_student
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch student details'
        }), 500


@students_bp.route('/<student_id>/enrollments', methods=['GET'])
@login_required
def get_student_enrollments(student_id):
    """
    Get all enrollments for a specific student.

    Args:
        student_id: The student's GUID

    Returns:
        JSON response with enrollment list
    """
    try:
        # Initialize API client with user's token
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Verify student belongs to this department
        users = client.get_users_by_department(g.department_id)
        student_id_lower = student_id.lower()
        student_found = any(
            (user.get('id') or user.get('Id') or '').lower() == student_id_lower
            for user in users
        )

        if not student_found:
            return jsonify({
                'success': False,
                'error': 'Student not found in your department'
            }), 404

        # Get enrollments
        enrollments = client.get_user_enrollments(student_id)

        # Format enrollments (Absorb API field names)
        formatted_enrollments = []
        for enrollment in enrollments:
            # Extract values with correct Absorb API field names
            progress_val = enrollment.get('progress', 0)
            time_spent_val = enrollment.get('timeSpent') or '0'  # HH:MM:SS string
            status_val = enrollment.get('status', 0)
            course_name = enrollment.get('courseName') or 'Unknown Course'
            enrollment_id = enrollment.get('id')
            course_id = enrollment.get('courseId')

            # Date fields from Absorb API
            date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
            date_completed = enrollment.get('dateCompleted')
            # accessDate is often None, fallback to dateEdited or dateStarted
            date_last_accessed = (enrollment.get('accessDate') or
                                  enrollment.get('dateEdited') or
                                  enrollment.get('dateStarted'))

            progress_info = format_progress(progress_val)
            formatted_enrollments.append({
                'id': enrollment_id,
                'courseId': course_id,
                'courseName': course_name,
                'progress': progress_info,
                'timeSpent': {
                    'minutes': time_spent_val,
                    'formatted': format_time_spent(time_spent_val)
                },
                'status': status_val,
                'statusText': get_enrollment_status_text(status_val),
                'enrolledDate': format_datetime(parse_absorb_date(date_enrolled)),
                'completedDate': format_datetime(parse_absorb_date(date_completed)),
                'lastAccessed': {
                    'formatted': format_datetime(parse_absorb_date(date_last_accessed)),
                    'relative': format_relative_time(parse_absorb_date(date_last_accessed))
                }
            })

        return jsonify({
            'success': True,
            'enrollments': formatted_enrollments,
            'count': len(formatted_enrollments)
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch enrollments'
        }), 500
