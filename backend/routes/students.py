"""Student detail routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g, request
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
    format_relative_time,
    validate_email,
    sanitize_string
)
from utils.formatters import parse_time_spent_to_minutes
from utils.readiness import calculate_readiness
from utils.gap_metrics import calculate_gap_metrics
from demo_data import is_demo_student, get_real_id, get_demo_name, is_demo_cache_valid, DEMO_DEPT_ID


def is_prelicensing_course(name):
    """Check if course is pre-licensing related."""
    if not name:
        return False
    lower = name.lower()
    if 'pre-licens' in lower or 'prelicens' in lower or 'pre licens' in lower:
        return True
    # Also match courses containing "license"/"licensing" (broader catch)
    # but exclude exam prep courses
    if 'licens' in lower:
        if not ('prep' in lower or 'practice' in lower or 'study' in lower):
            return True
    return False


def is_chapter_or_module(name):
    """Check if course is a chapter/module."""
    if not name:
        return False
    lower = name.lower()
    return ('module' in lower or 'chapter' in lower or 'lesson' in lower or 'unit' in lower)


def is_exam_prep_course(name):
    """Check if course is an exam prep course (excludes practice exams)."""
    if not name:
        return False
    lower = name.lower()
    if 'practice' in lower:
        return False
    return 'prep' in lower or 'study' in lower


def calculate_prelicensing_totals(enrollments):
    """
    Calculate total time spent and average progress across all pre-licensing courses.
    Returns: (total_time_minutes, average_progress, course_name, primary_status)
    """
    prelicensing_enrollments = []
    main_course_name = "Pre-License Course"
    primary_status = 0

    for e in enrollments:
        name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
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
            time_val = 0
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        time_val = parsed
                        break
            progress = e.get('progress', 0)
            return time_val, progress, e.get('name') or e.get('Name') or e.get('courseName') or 'No Course', e.get('status', 0)
        return 0, 0, 'No Course', 0

    # Get the main course's time and progress (not chapters/modules)
    main_course_time = 0
    main_course_progress = None

    for e in prelicensing_enrollments:
        name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
        if is_prelicensing_course(name) and not is_chapter_or_module(name):
            # Use the main prelicensing course's time directly
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        main_course_time = parsed
                        break
            progress = e.get('progress', 0)
            if isinstance(progress, (int, float)):
                main_course_progress = progress

    # If no main course found, fall back to summing all chapters
    if main_course_time == 0:
        for e in prelicensing_enrollments:
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        main_course_time += parsed
                        break

    # Use main course progress directly; fall back to average only if no main course found
    if main_course_progress is not None:
        final_progress = main_course_progress
    else:
        progress_values = []
        for e in prelicensing_enrollments:
            progress = e.get('progress', 0)
            if isinstance(progress, (int, float)):
                progress_values.append(progress)
        final_progress = sum(progress_values) / len(progress_values) if progress_values else 0

    return main_course_time, final_progress, main_course_name, primary_status

students_bp = Blueprint('students', __name__)


def _demo_student_detail(student_id):
    """Fetch real Absorb data for a demo student and return anonymized response."""
    real_id = get_real_id(student_id)
    if not real_id:
        return jsonify({'success': False, 'error': 'Demo student not found'}), 404

    try:
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)
        student = client.get_user_by_id(real_id)
        enrollments = client.get_user_enrollments(real_id)
    except (AbsorbAPIError, Exception):
        return jsonify({'success': False, 'error': 'Student data not available'}), 404

    # Format enrollments (same as real path)
    formatted_enrollments = []
    for enrollment in enrollments:
        progress_val = enrollment.get('progress', 0)
        time_spent_val = '0'
        for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
            _tv = enrollment.get(_tf)
            if _tv and parse_time_spent_to_minutes(_tv) > 0:
                time_spent_val = _tv
                break
        status_val = enrollment.get('status', 0)
        course_name = enrollment.get('name') or enrollment.get('Name') or enrollment.get('courseName') or enrollment.get('CourseName') or 'Unknown Course'
        date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
        date_completed = enrollment.get('dateCompleted')
        date_last_accessed = enrollment.get('accessDate') or enrollment.get('dateEdited') or enrollment.get('dateStarted')
        time_spent_minutes = parse_time_spent_to_minutes(time_spent_val)
        formatted_enrollments.append({
            'id': enrollment.get('id'),
            'courseId': enrollment.get('courseId'),
            'courseName': course_name,
            'progress': format_progress(progress_val),
            'timeSpent': {'minutes': time_spent_minutes, 'formatted': format_time_spent(time_spent_val)},
            'status': status_val,
            'statusText': get_enrollment_status_text(status_val),
            'enrolledDate': format_datetime(parse_absorb_date(date_enrolled)),
            'completedDate': format_datetime(parse_absorb_date(date_completed)),
            'lastAccessed': {
                'formatted': format_datetime(parse_absorb_date(date_last_accessed)),
                'relative': format_relative_time(parse_absorb_date(date_last_accessed))
            }
        })
    formatted_enrollments.sort(key=lambda e: (0 if e['status'] == 1 else 1, -e['progress']['value']))

    # Calculate totals
    total_time, avg_progress, course_name_calc, primary_status = calculate_prelicensing_totals(enrollments)
    exam_prep_time = 0
    for e in enrollments:
        e_name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
        if is_exam_prep_course(e_name) and not is_prelicensing_course(e_name):
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        exam_prep_time += parsed
                        break

    student['enrollments'] = enrollments
    student['progress'] = avg_progress
    student['timeSpent'] = total_time
    student['examPrepTime'] = exam_prep_time
    student['courseName'] = course_name_calc
    student['enrollmentStatus'] = primary_status

    formatted_student = format_student_for_response(student)

    # Anonymize personal info
    first, last, demo_email = get_demo_name(student_id)
    formatted_student['id'] = student_id
    formatted_student['firstName'] = first
    formatted_student['lastName'] = last
    formatted_student['fullName'] = f'{first} {last}'
    formatted_student['email'] = demo_email
    formatted_student['phone'] = ''
    formatted_student['username'] = ''
    formatted_student.pop('_realEmail', None)

    formatted_student['enrollments'] = formatted_enrollments
    formatted_student['totalEnrollments'] = len(enrollments)
    formatted_student['completedEnrollments'] = sum(1 for e in enrollments if e.get('status') in [2, 3])
    course_type = request.args.get('courseType', '')
    formatted_student['readiness'] = calculate_readiness(enrollments, course_type=course_type)
    formatted_student['gapMetrics'] = calculate_gap_metrics(enrollments)
    return jsonify({'success': True, 'student': formatted_student})


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
    # Demo student — fetch real data from Absorb, anonymize personal info
    if is_demo_student(student_id):
        return _demo_student_detail(student_id)

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

        # If not found in department, try direct fetch by ID (works for admin users across departments)
        if not student:
            print(f"[STUDENT DETAIL] Student {student_id} not in department {g.department_id}, trying direct fetch...")
            try:
                student = client.get_user_by_id(student_id)
                print(f"[STUDENT DETAIL] Successfully fetched cross-department student: {student.get('emailAddress', 'unknown')}")
            except AbsorbAPIError as e:
                print(f"[STUDENT DETAIL] Direct fetch failed: {e}")
                # Might be a demo student on a different worker — rebuild demo cache
                if not is_demo_cache_valid():
                    try:
                        from routes.dashboard import get_cached_students
                        get_cached_students(DEMO_DEPT_ID, g.absorb_token)
                    except Exception:
                        pass
                    if is_demo_student(student_id):
                        return _demo_student_detail(student_id)
                return jsonify({
                    'success': False,
                    'error': 'Student not found'
                }), 404

        # Get all enrollments for this student
        enrollments = client.get_user_enrollments(student_id)

        # Format enrollments (Absorb API field names)
        formatted_enrollments = []
        for enrollment in enrollments:
            # Extract values with correct Absorb API field names
            progress_val = enrollment.get('progress', 0)
            # Try each time field, use first non-zero to avoid truthy "00:00:00" short-circuiting
            time_spent_val = '0'
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = enrollment.get(_tf)
                if _tv and parse_time_spent_to_minutes(_tv) > 0:
                    time_spent_val = _tv
                    break
            status_val = enrollment.get('status', 0)
            course_name = enrollment.get('name') or enrollment.get('Name') or enrollment.get('courseName') or enrollment.get('CourseName') or 'Unknown Course'
            enrollment_id = enrollment.get('id')
            course_id = enrollment.get('courseId')

            # Date fields from Absorb API
            date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
            date_completed = enrollment.get('dateCompleted')
            # accessDate is often None, fallback to dateEdited or dateStarted
            date_last_accessed = (enrollment.get('accessDate') or
                                  enrollment.get('dateEdited') or
                                  enrollment.get('dateStarted'))

            time_spent_minutes = parse_time_spent_to_minutes(time_spent_val)
            progress_info = format_progress(progress_val)
            formatted_enrollments.append({
                'id': enrollment_id,
                'courseId': course_id,
                'courseName': course_name,
                'progress': progress_info,
                'timeSpent': {
                    'minutes': time_spent_minutes,
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

        # Calculate exam prep time (all non-prelicensing prep/study courses)
        exam_prep_time = 0
        for e in enrollments:
            e_name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
            if is_exam_prep_course(e_name) and not is_prelicensing_course(e_name):
                for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                    _tv = e.get(_tf)
                    if _tv:
                        parsed = parse_time_spent_to_minutes(_tv)
                        if parsed > 0:
                            exam_prep_time += parsed
                            break

        # Add enrollment data to student with calculated totals
        student['enrollments'] = enrollments
        student['progress'] = avg_progress
        student['timeSpent'] = total_time  # Already in minutes
        student['examPrepTime'] = exam_prep_time
        student['courseName'] = course_name
        student['enrollmentStatus'] = primary_status

        # Format basic student info
        formatted_student = format_student_for_response(student)

        # Add detailed enrollment data
        formatted_student['enrollments'] = formatted_enrollments
        formatted_student['totalEnrollments'] = len(enrollments)
        # Count completed (status 2 or 3 - Absorb uses 3 for completed)
        formatted_student['completedEnrollments'] = sum(1 for e in enrollments if e.get('status') in [2, 3])

        # Calculate readiness from raw enrollments
        # course_type from query param (passed by frontend from exam sheet data)
        course_type = request.args.get('courseType', '')
        formatted_student['readiness'] = calculate_readiness(
            enrollments, course_type=course_type
        )
        formatted_student['gapMetrics'] = calculate_gap_metrics(enrollments)

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


@students_bp.route('/<student_id>', methods=['PUT'])
@login_required
def update_student_contact(student_id):
    """Update contact info for a specific student."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Request body required'}), 400

        # Build updates dict with Absorb API field names (PascalCase)
        updates = {}

        if 'firstName' in data:
            first_name = sanitize_string(data['firstName'])
            if not first_name:
                return jsonify({'success': False, 'error': 'First name cannot be empty'}), 400
            if len(first_name) > 100:
                return jsonify({'success': False, 'error': 'First name is too long'}), 400
            updates['FirstName'] = first_name

        if 'lastName' in data:
            last_name = sanitize_string(data['lastName'])
            if not last_name:
                return jsonify({'success': False, 'error': 'Last name cannot be empty'}), 400
            if len(last_name) > 100:
                return jsonify({'success': False, 'error': 'Last name is too long'}), 400
            updates['LastName'] = last_name

        if 'emailAddress' in data:
            email = sanitize_string(data['emailAddress'])
            is_valid, error_msg = validate_email(email)
            if not is_valid:
                return jsonify({'success': False, 'error': error_msg}), 400
            updates['EmailAddress'] = email

        if 'phone' in data:
            phone = sanitize_string(data['phone'])
            if len(phone) > 30:
                return jsonify({'success': False, 'error': 'Phone number is too long'}), 400
            updates['Phone'] = phone

        if not updates:
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

        # Initialize API client
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Verify student access (same pattern as get_student_details)
        users = client.get_users_by_department(g.department_id)
        student_id_lower = student_id.lower()
        student_found = any(
            (user.get('id') or user.get('Id') or '').lower() == student_id_lower
            for user in users
        )

        if not student_found:
            try:
                client.get_user_by_id(student_id)
            except AbsorbAPIError:
                return jsonify({'success': False, 'error': 'Student not found'}), 404

        # Perform the update
        updated_user = client.update_user(student_id, updates)

        return jsonify({
            'success': True,
            'student': {
                'id': updated_user.get('id') or updated_user.get('Id') or student_id,
                'firstName': updated_user.get('firstName') or updated_user.get('FirstName') or '',
                'lastName': updated_user.get('lastName') or updated_user.get('LastName') or '',
                'emailAddress': updated_user.get('emailAddress') or updated_user.get('EmailAddress') or '',
                'phone': updated_user.get('phone') or updated_user.get('Phone') or '',
            }
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        print(f"[STUDENT UPDATE] Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update student'
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

        # If not found in department, try direct fetch by ID (works for admin users across departments)
        if not student_found:
            print(f"[STUDENT ENROLLMENTS] Student {student_id} not in department {g.department_id}, trying direct fetch...")
            try:
                # Try to fetch the student directly to verify access
                student = client.get_user_by_id(student_id)
                print(f"[STUDENT ENROLLMENTS] Successfully verified cross-department student: {student.get('emailAddress', 'unknown')}")
                student_found = True
            except AbsorbAPIError as e:
                print(f"[STUDENT ENROLLMENTS] Direct fetch failed: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Student not found'
                }), 404

        if not student_found:
            return jsonify({
                'success': False,
                'error': 'Student not found'
            }), 404

        # Get enrollments
        enrollments = client.get_user_enrollments(student_id)

        # Format enrollments (Absorb API field names)
        formatted_enrollments = []
        for enrollment in enrollments:
            # Extract values with correct Absorb API field names
            progress_val = enrollment.get('progress', 0)
            # Try each time field, use first non-zero to avoid truthy "00:00:00" short-circuiting
            time_spent_val = '0'
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = enrollment.get(_tf)
                if _tv and parse_time_spent_to_minutes(_tv) > 0:
                    time_spent_val = _tv
                    break
            status_val = enrollment.get('status', 0)
            course_name = enrollment.get('name') or enrollment.get('Name') or enrollment.get('courseName') or enrollment.get('CourseName') or 'Unknown Course'
            enrollment_id = enrollment.get('id')
            course_id = enrollment.get('courseId')

            # Date fields from Absorb API
            date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
            date_completed = enrollment.get('dateCompleted')
            # accessDate is often None, fallback to dateEdited or dateStarted
            date_last_accessed = (enrollment.get('accessDate') or
                                  enrollment.get('dateEdited') or
                                  enrollment.get('dateStarted'))

            time_spent_minutes = parse_time_spent_to_minutes(time_spent_val)
            progress_info = format_progress(progress_val)
            formatted_enrollments.append({
                'id': enrollment_id,
                'courseId': course_id,
                'courseName': course_name,
                'progress': progress_info,
                'timeSpent': {
                    'minutes': time_spent_minutes,
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
