"""Student detail routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g, request
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils.absorb_retry import absorb_retry_on_401
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
from demo_data import is_demo_student, get_demo_student_detail, DEMO_DEPT_ID


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
    """Check if course is an exam prep course (includes practice exams)."""
    if not name:
        return False
    lower = name.lower()
    return 'prep' in lower or 'study' in lower or 'practice' in lower


def calculate_prelicensing_totals(enrollments):
    """
    Calculate total time spent and average progress across all pre-licensing courses.
    Returns: (total_time_minutes, average_progress, course_name, primary_status)
    """
    prelicensing_enrollments = []
    main_course_name = "Pre-License Course"
    main_course_names = []  # all main pre-license course names (dual Life+Health states)
    primary_status = 0

    for e in enrollments:
        name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
        if is_prelicensing_course(name) or is_chapter_or_module(name):
            prelicensing_enrollments.append(e)
            # Track main course name (not a module/chapter)
            if is_prelicensing_course(name) and not is_chapter_or_module(name):
                main_course_name = name
                if name:
                    main_course_names.append(name)
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

    # Sum time and average progress across ALL main pre-license courses.
    # States like Michigan have SEPARATE Life and Health pre-license courses;
    # a student enrolled in both has two main courses. Absorb reports each
    # main course's timeSpent as a rollup of its OWN chapters, so summing the
    # two mains is correct (no double-count between Life and Health). Using a
    # single main (the old behavior) undercounted dual-enrolled students.
    main_course_time = 0
    main_course_progress = None
    _main_progress_values = []

    for e in prelicensing_enrollments:
        name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
        if is_prelicensing_course(name) and not is_chapter_or_module(name):
            # Add this main course's time to the running total
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        main_course_time += parsed
                        break
            progress = e.get('progress', 0)
            if isinstance(progress, (int, float)):
                _main_progress_values.append(progress)

    # Average progress across the main course(s) — for a single-course student
    # this is just that course's progress; for dual Life+Health it's the mean.
    if _main_progress_values:
        main_course_progress = sum(_main_progress_values) / len(_main_progress_values)

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

    # Dual Life+Health (separate-course states): show a combined name so the
    # modal header reflects the combined enrollment rather than one line.
    from absorb_api import combined_prelicense_name
    _combined = combined_prelicense_name(main_course_names)
    if _combined:
        main_course_name = _combined

    return main_course_time, final_progress, main_course_name, primary_status

students_bp = Blueprint('students', __name__)


def _demo_student_detail(student_id):
    """Return pre-computed detail for a demo student from static snapshot."""
    detail = get_demo_student_detail(student_id)
    if not detail:
        return jsonify({'success': False, 'error': 'Demo student not found'}), 404
    return jsonify({'success': True, 'student': detail})


@students_bp.route('/<student_id>', methods=['GET'])
@login_required
@absorb_retry_on_401
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

        # Fetch the student DIRECTLY by ID — one lightweight /users/{id} call.
        # Previously this fetched the ENTIRE department user list
        # (get_users_by_department) just to locate one student. On a large dept
        # (1,000+ users) that re-ran the whole lastLoginDate bucket-split fetch
        # on every modal open: slow (~10s, "freezes") and fragile (it 401'd
        # under token churn and failed the modal entirely). The student's GUID
        # already comes from the dashboard list the user loaded, so a single
        # by-id fetch is all we need — and on a 401 the retry decorator only has
        # to refresh + replay one light call, not a 14-bucket fan-out.
        try:
            student = client.get_user_by_id(student_id)
        except AbsorbAPIError as e:
            # A 401 is a stale token, not a missing student — re-raise so the
            # @absorb_retry_on_401 decorator refreshes + retries instead of
            # returning a misleading 404.
            if e.status_code == 401:
                raise
            print(f"[STUDENT DETAIL] Direct fetch failed for {student_id}: {e}")
            return jsonify({
                'success': False,
                'error': 'Student not found'
            }), 404
        if not student:
            return jsonify({
                'success': False,
                'error': 'Student not found'
            }), 404

        # Get all enrollments for this student
        enrollments = client.get_user_enrollments(student_id)

        # STAGING DIAGNOSTIC: dump enrollment names + raw time fields + video
        # classification for the watched student so we can see whether video
        # time lives at the enrollment level (rollup) or only at the lesson
        # level (like practice-exam attempts).
        import os as _os
        _watch = (_os.getenv('DEBUG_WATCH_EMAIL') or '').lower().strip()
        if _watch:
            _semail = (student.get('emailAddress') or student.get('EmailAddress') or '').lower().strip()
            if _semail == _watch:
                from utils.readiness import (
                    _is_video_course as _ivc,
                    _is_life_video as _ilv,
                    _is_health_video as _ihv,
                    _get_enrollment_minutes as _gem,
                )
                print(f"[WATCH-ENROLL] {_semail} has {len(enrollments)} enrollments:")
                for _e in enrollments:
                    _n = _e.get('name') or _e.get('Name') or _e.get('courseName') or _e.get('CourseName') or '?'
                    _p = _e.get('progress') or _e.get('Progress') or 0
                    _st = _e.get('status') or _e.get('Status') or 0
                    # raw time fields exactly as Absorb returned them
                    _raw = {_tf: _e.get(_tf) for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime') if _e.get(_tf) is not None}
                    _mins = round(_gem(_e), 1)
                    _vid = _ivc(_n)
                    _lvid = _ilv(_n)
                    _hvid = _ihv(_n)
                    _cid = _e.get('courseId') or _e.get('CourseId') or _e.get('course_id')
                    print(f"[WATCH-ENROLL]   name={_n!r} progress={_p} status={_st} "
                          f"mins={_mins} raw_time={_raw} video={_vid} life_vid={_lvid} health_vid={_hvid} courseId={_cid}")

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

        # Calculate exam prep time — main exam prep COURSES only (bundles).
        # Per product convention, the main exam prep course is named ending
        # with "Exam Prep" (e.g., "Texas Life & Health Exam Prep"). Absorb
        # reports that parent bundle's timeSpent as an aggregated rollup of
        # its sub-components (walkthrough videos, study guides, practice
        # exams, flashcards, content outlines, etc.). Those sub-components
        # match the broader is_exam_prep_course test (they contain 'prep',
        # 'practice', or 'study') but their time is already inside the
        # parent's rollup — summing both double-counts.
        main_exam_prep_total = 0
        fallback_sum = 0
        for e in enrollments:
            e_name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
            if not is_exam_prep_course(e_name) or is_prelicensing_course(e_name):
                continue
            _min = 0
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = e.get(_tf)
                if _tv:
                    parsed = parse_time_spent_to_minutes(_tv)
                    if parsed > 0:
                        _min = parsed
                        break
            # Main bundle course: name ends with "exam prep" (ignoring case
            # and incidental trailing punctuation/whitespace).
            name_clean = e_name.lower().strip().rstrip('.').rstrip()
            if name_clean.endswith('exam prep'):
                main_exam_prep_total += _min
            fallback_sum += _min
        # Prefer the main-bundle total; fall back to the legacy sum if no
        # bundle course is found (safety net for non-standard course names).
        exam_prep_time = main_exam_prep_total if main_exam_prep_total > 0 else fallback_sum

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

        # Fetch practice-exam attempt history in parallel and attach to the
        # matching enrollment records.
        practice_candidates = [
            e for e in enrollments
            if is_exam_prep_course(e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or '')
        ]
        print(f"[ATTEMPTS] Student {student_id}: {len(practice_candidates)} practice-exam enrollments found")
        for _pc in practice_candidates:
            _cname = _pc.get('name') or _pc.get('Name') or _pc.get('courseName') or _pc.get('CourseName') or ''
            _cid = _pc.get('courseId') or _pc.get('CourseId') or _pc.get('course_id')
            _eid = _pc.get('id') or _pc.get('Id')
            print(f"[ATTEMPTS]   enrollment '{_cname}' id={_eid} courseId={_cid}")
        practice_enrollments_with_ids = [
            e for e in practice_candidates
            if (e.get('courseId') or e.get('CourseId') or e.get('course_id'))
        ]
        print(f"[ATTEMPTS] {len(practice_enrollments_with_ids)} have a courseId — fetching attempts")
        if practice_enrollments_with_ids:
            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
            def _fetch_attempts(enr):
                cid = enr.get('courseId') or enr.get('CourseId') or enr.get('course_id')
                attempts = client.get_practice_exam_attempts(student_id, cid)
                print(f"[ATTEMPTS]   courseId={cid} -> {len(attempts)} attempt(s) returned")
                return enr, attempts
            with _TPE(max_workers=min(8, len(practice_enrollments_with_ids))) as _ex:
                _futs = {_ex.submit(_fetch_attempts, e): e for e in practice_enrollments_with_ids}
                for _f in _ac(_futs):
                    try:
                        enr, attempts = _f.result()
                        if attempts:
                            enr['attempts'] = attempts
                    except Exception as _e:
                        print(f"[ATTEMPTS] fetch failed: {_e}")

        # Calculate readiness from raw enrollments. Course type is derived from
        # Absorb inside calculate_readiness (single source of truth) — we no
        # longer pass the sheet-derived courseType query param.
        formatted_student['readiness'] = calculate_readiness(enrollments)
        formatted_student['gapMetrics'] = calculate_gap_metrics(enrollments)

        return jsonify({
            'success': True,
            'student': formatted_student
        })

    except AbsorbAPIError as e:
        # A 401 means the Absorb token went stale. Re-raise so the
        # @absorb_retry_on_401 decorator transparently refreshes the token
        # and retries the whole route. Without this, the route returns 401
        # to the frontend, which auto-logs-the-user-out — making a routine
        # token expiry look like the modal "crashing". Non-401 errors still
        # surface normally.
        if e.status_code == 401:
            raise
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
@absorb_retry_on_401
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
@absorb_retry_on_401
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
