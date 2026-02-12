"""Exam scheduling routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g, request
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils import format_student_for_response
from google_sheets import fetch_exam_sheet, invalidate_sheet_cache, parse_exam_date_for_sort
from utils.readiness import calculate_readiness
from utils.gap_metrics import calculate_gap_metrics

exam_bp = Blueprint('exam', __name__)

ADMIN_PASSWORD = os.environ.get('EXAM_ADMIN_PASSWORD', 'Justinsurance123$')

# Cache for department names (departmentId -> name)
_dept_name_cache = {}

# Cache for processed exam students (email -> {'raw': ..., 'formatted': ...})
_exam_absorb_cache = {}
_exam_absorb_timestamp = None
EXAM_ABSORB_CACHE_TTL = 300  # 5 minutes

# In-memory pass/fail overrides (email -> 'PASS'|'FAIL')
_passfail_overrides = {}

# In-memory exam date overrides (email -> {'date': 'YYYY-MM-DD', 'time': 'HH:MM AM/PM'})
_exam_date_overrides = {}

# In-memory exam result snapshots (email -> list of snapshot dicts)
_exam_result_snapshots = {}


def get_department_name(client, department_id):
    """Get department name from Absorb, with caching."""
    if not department_id:
        return 'Unknown'

    if department_id in _dept_name_cache:
        return _dept_name_cache[department_id]

    try:
        dept = client.get_department(department_id)
        name = dept.get('name') or dept.get('Name') or 'Unknown'
        _dept_name_cache[department_id] = name
        return name
    except Exception:
        _dept_name_cache[department_id] = 'Unknown'
        return 'Unknown'


def is_exam_absorb_cache_valid():
    """Check if the exam Absorb cache is still valid."""
    global _exam_absorb_timestamp
    if not _exam_absorb_timestamp:
        return False
    age = (datetime.utcnow() - _exam_absorb_timestamp).total_seconds()
    return age < EXAM_ABSORB_CACHE_TTL


def invalidate_exam_absorb_cache():
    """Clear the exam Absorb lookup cache."""
    global _exam_absorb_cache, _exam_absorb_timestamp
    _exam_absorb_cache = {}
    _exam_absorb_timestamp = None
    print("[EXAM] Absorb cache invalidated")


@exam_bp.route('/students', methods=['GET'])
@login_required
def get_exam_students():
    """Get exam-scheduled students matched with their Absorb data."""
    try:
        # Check admin mode
        admin_key = request.args.get('adminKey', '')
        is_admin = admin_key == ADMIN_PASSWORD

        # 1. Fetch Google Sheet data
        sheet_students = fetch_exam_sheet()

        if not sheet_students:
            return jsonify({
                'success': True,
                'students': [],
                'examSummary': _empty_summary(),
                'count': 0
            })

        # 2. Get cached Absorb students from current department (fast match)
        from routes.dashboard import get_cached_students
        raw_students, formatted_students = get_cached_students(
            g.department_id, g.absorb_token
        )

        # 3. Build email maps from current department cache
        raw_email_map = {}
        for s in raw_students:
            email = (s.get('emailAddress') or '').lower().strip()
            if email:
                raw_email_map[email] = s

        formatted_email_map = {}
        for s in formatted_students:
            email = (s.get('email') or '').lower().strip()
            if email:
                formatted_email_map[email] = s

        # 4. Find emails that need cross-department lookup
        sheet_emails = set(s['email'] for s in sheet_students)
        matched_emails = sheet_emails & set(formatted_email_map.keys())
        unmatched_emails = sheet_emails - matched_emails

        print(f"[EXAM] Current department ID: {g.department_id}")
        print(f"[EXAM] Total sheet emails: {len(sheet_emails)}, Matched in dept: {len(matched_emails)}, Unmatched: {len(unmatched_emails)}")
        if len(unmatched_emails) > 0 and len(unmatched_emails) <= 5:
            print(f"[EXAM] Unmatched emails sample: {list(unmatched_emails)[:5]}")

        # Create client with user token (admin users can access cross-department data)
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # 5. For admin mode: fetch ONLY the specific students by email (cross-department)
        # Admin users' tokens have cross-department access
        if is_admin and unmatched_emails:
            global _exam_absorb_timestamp
            print(f"[EXAM] Admin mode: Fetching {len(unmatched_emails)} specific students across all departments...")
            print(f"[EXAM] Using admin token (has cross-dept access)")

            # Fetch users by searching all departments (admin token allows this)
            unmatched_email_list = list(unmatched_emails)
            found_users = client.get_users_by_emails_batch(unmatched_email_list)
            print(f"[EXAM] Found {len(found_users)} users, processing enrollments...")

            # Process found users in parallel to get enrollment data
            found = 0

            if len(found_users) > 0:
                max_workers = min(50, len(found_users))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit enrollment processing for each found user (using admin token)
                    future_to_user = {
                        executor.submit(client._process_single_user, user): user
                        for user in found_users
                    }

                    completed = 0
                    for future in as_completed(future_to_user):
                        completed += 1
                        user = future_to_user[future]
                        email = (user.get('emailAddress') or user.get('EmailAddress') or '').lower().strip()
                        try:
                            result = future.result()
                            if result:
                                formatted = format_student_for_response(result)
                                _exam_absorb_cache[email] = {
                                    'raw': result,
                                    'formatted': formatted
                                }
                                found += 1
                            else:
                                _exam_absorb_cache[email] = None
                        except Exception as e:
                            print(f"[EXAM] Error processing {email}: {e}")
                            _exam_absorb_cache[email] = None

                        if completed % 20 == 0 or completed == len(found_users):
                            print(f"[EXAM] Processed {completed}/{len(found_users)} enrollments ({found} complete)")

            # Cache remaining unmatched as None
            for email in unmatched_emails:
                if email not in _exam_absorb_cache:
                    _exam_absorb_cache[email] = None

            _exam_absorb_timestamp = datetime.utcnow()
            print(f"[EXAM] Admin fetch complete: {found}/{len(unmatched_emails)} found across all departments")

        # 6. Build combined exam student list
        exam_students = []

        for sheet_student in sheet_students:
            email = sheet_student['email']

            # Try department cache first
            formatted = formatted_email_map.get(email)
            raw = raw_email_map.get(email)

            if formatted and raw:
                # Found in current department
                dept_id = raw.get('departmentId') or ''
                dept_name = get_department_name(client, dept_id) if dept_id else g.user.get('departmentName', 'Unknown')
                raw_enrollments = raw.get('enrollments', [])

                exam_entry = _build_exam_entry(formatted, sheet_student, dept_name, True, raw_enrollments)
            elif email in _exam_absorb_cache and _exam_absorb_cache[email] is not None:
                # Found via cross-department lookup
                cached = _exam_absorb_cache[email]
                dept_id = cached['raw'].get('departmentId') or ''
                # Admin token has cross-department access
                dept_name = get_department_name(client, dept_id) if dept_id else 'Unknown'
                raw_enrollments = cached['raw'].get('enrollments', [])

                exam_entry = _build_exam_entry(cached['formatted'], sheet_student, dept_name, True, raw_enrollments)
            else:
                # Not found in Absorb at all
                exam_entry = _build_unmatched_entry(sheet_student)

            # Apply any pass/fail overrides
            if email in _passfail_overrides:
                exam_entry['passFail'] = _passfail_overrides[email]

            # Apply any exam date overrides
            if email in _exam_date_overrides:
                override = _exam_date_overrides[email]
                exam_entry['examDateRaw'] = override['date']
                exam_entry['examTime'] = override.get('time', '')
                # Format the date for display (e.g., "Jan 15, 2026")
                try:
                    dt = datetime.strptime(override['date'], '%Y-%m-%d')
                    exam_entry['examDate'] = dt.strftime('%b %d, %Y')
                except:
                    exam_entry['examDate'] = override['date']

            # Include full sheet tracking data in admin mode
            if is_admin:
                exam_entry['sheetTracking'] = _build_tracking_data(sheet_student)

            exam_students.append(exam_entry)

        # 7. Sort: upcoming first, then past
        now = datetime.utcnow()

        def sort_key(s):
            dt = parse_exam_date_for_sort(s.get('examDateRaw', ''))
            is_past = dt < now if dt != datetime.min else True
            return (is_past, dt if not is_past else datetime.max - dt)

        exam_students.sort(key=sort_key)

        # 8. Calculate exam KPIs
        exam_summary = _calculate_exam_summary(exam_students, now)

        return jsonify({
            'success': True,
            'students': exam_students,
            'examSummary': exam_summary,
            'count': len(exam_students)
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        import traceback
        print(f"[EXAM] Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to fetch exam students: {str(e)}'
        }), 500


def _build_exam_entry(formatted, sheet_student, dept_name, matched, raw_enrollments=None):
    """Build an exam entry from formatted Absorb data + sheet data."""
    entry = {
        **formatted,
        'examDate': sheet_student['examDateFormatted'],
        'examDateRaw': sheet_student['examDate'],
        'examTime': sheet_student['examTime'],
        'examState': sheet_student['state'],
        'examCourse': sheet_student['course'],
        'agencyOwner': sheet_student['agencyOwner'],
        'passFail': sheet_student['passFail'],
        'finalOutcome': sheet_student['finalOutcome'],
        'departmentName': dept_name,
        'matched': matched
    }

    # Calculate readiness if we have enrollment data
    if raw_enrollments:
        days_until = None
        exam_date_raw = sheet_student.get('examDate', '')
        if exam_date_raw:
            try:
                dt = parse_exam_date_for_sort(exam_date_raw)
                if dt != datetime.min:
                    delta = dt - datetime.utcnow()
                    days_until = delta.days
            except Exception:
                pass
        entry['readiness'] = calculate_readiness(
            raw_enrollments,
            course_type=sheet_student.get('course', ''),
            days_until_exam=days_until
        )
        entry['gapMetrics'] = calculate_gap_metrics(raw_enrollments)

    return entry


def _build_unmatched_entry(sheet_student):
    """Build an exam entry for a student not found in Absorb."""
    return {
        'id': None,
        'fullName': sheet_student['name'],
        'email': sheet_student['email'],
        'status': {
            'status': 'UNKNOWN',
            'class': 'gray',
            'emoji': '',
            'priority': 99
        },
        'lastLogin': {
            'raw': None,
            'formatted': 'N/A',
            'relative': 'N/A'
        },
        'progress': {
            'value': 0,
            'display': '0%',
            'colorClass': 'low',
            'color': '#ef4444'
        },
        'courseName': 'Not in Absorb',
        'timeSpent': {'minutes': 0, 'formatted': '0m'},
        'examPrepTime': {'minutes': 0, 'formatted': '0m'},
        'examDate': sheet_student['examDateFormatted'],
        'examDateRaw': sheet_student['examDate'],
        'examTime': sheet_student['examTime'],
        'examState': sheet_student['state'],
        'examCourse': sheet_student['course'],
        'agencyOwner': sheet_student['agencyOwner'],
        'passFail': sheet_student['passFail'],
        'finalOutcome': sheet_student['finalOutcome'],
        'departmentName': 'Not in Absorb',
        'matched': False
    }


def _build_tracking_data(sheet_student):
    """Build the extended tracking data from the Google Sheet for admin view."""
    return {
        'phone': sheet_student.get('phone', ''),
        'alertDate': sheet_student.get('alertDate', ''),
        'studyHoursAtExam': sheet_student.get('studyHoursAtExam', ''),
        'finalPractice': sheet_student.get('finalPractice', ''),
        'chaptersComplete': sheet_student.get('chaptersComplete', ''),
        'videosWatched': sheet_student.get('videosWatched', ''),
        'stateLawsDone': sheet_student.get('stateLawsDone', ''),
        'studyConsistency': sheet_student.get('studyConsistency', ''),
        't0Sent': sheet_student.get('t0Sent', ''),
        'weeklyTracking': sheet_student.get('weeklyTracking', []),
    }


def _calculate_exam_summary(exam_students, now):
    """Calculate comprehensive KPI summary for exam students."""
    total = len(exam_students)
    passed_students = [s for s in exam_students if (s.get('passFail') or '').upper() == 'PASS']
    failed_students = [s for s in exam_students if (s.get('passFail') or '').upper() == 'FAIL']
    passed = len(passed_students)
    failed = len(failed_students)

    upcoming = 0
    at_risk = 0  # upcoming exam but low progress
    for s in exam_students:
        dt = parse_exam_date_for_sort(s.get('examDateRaw', ''))
        has_result = bool(s.get('passFail', '').strip())
        if dt > now and not has_result:
            upcoming += 1
            # At risk: upcoming exam but < 80% progress (matched students only)
            if s.get('matched') and s.get('progress', {}).get('value', 0) < 80:
                at_risk += 1

    no_result = total - passed - failed - upcoming

    # Pass rate (of those who have taken the exam)
    completed_exams = passed + failed
    pass_rate = round((passed / completed_exams * 100), 1) if completed_exams > 0 else 0

    # Study time analytics (matched students only)
    matched_students = [s for s in exam_students if s.get('matched')]
    matched_passed = [s for s in passed_students if s.get('matched')]
    matched_failed = [s for s in failed_students if s.get('matched')]

    avg_progress = 0
    avg_study_time = 0
    avg_study_passed = 0
    avg_study_failed = 0

    if matched_students:
        avg_progress = round(
            sum(s['progress']['value'] for s in matched_students) / len(matched_students), 1
        )
        total_study = sum(
            (s.get('timeSpent', {}).get('minutes', 0) or 0) +
            (s.get('examPrepTime', {}).get('minutes', 0) or 0)
            for s in matched_students
        )
        avg_study_time = round(total_study / len(matched_students))

    if matched_passed:
        total_study_passed = sum(
            (s.get('timeSpent', {}).get('minutes', 0) or 0) +
            (s.get('examPrepTime', {}).get('minutes', 0) or 0)
            for s in matched_passed
        )
        avg_study_passed = round(total_study_passed / len(matched_passed))

    if matched_failed:
        total_study_failed = sum(
            (s.get('timeSpent', {}).get('minutes', 0) or 0) +
            (s.get('examPrepTime', {}).get('minutes', 0) or 0)
            for s in matched_failed
        )
        avg_study_failed = round(total_study_failed / len(matched_failed))

    # Course type breakdown
    course_types = {}
    for s in exam_students:
        course = (s.get('examCourse') or 'Unknown').strip()
        if course not in course_types:
            course_types[course] = {'total': 0, 'passed': 0, 'failed': 0}
        course_types[course]['total'] += 1
        pf = (s.get('passFail') or '').upper()
        if pf == 'PASS':
            course_types[course]['passed'] += 1
        elif pf == 'FAIL':
            course_types[course]['failed'] += 1

    # Format study times for display
    def format_mins(m):
        if m >= 60:
            return f"{m // 60}h {m % 60}m"
        return f"{m}m"

    return {
        'total': total,
        'upcoming': upcoming,
        'passed': passed,
        'failed': failed,
        'noResult': no_result,
        'passRate': pass_rate,
        'atRisk': at_risk,
        'averageProgress': avg_progress,
        'avgStudyTime': avg_study_time,
        'avgStudyTimeFormatted': format_mins(avg_study_time),
        'avgStudyPassed': avg_study_passed,
        'avgStudyPassedFormatted': format_mins(avg_study_passed),
        'avgStudyFailed': avg_study_failed,
        'avgStudyFailedFormatted': format_mins(avg_study_failed),
        'courseTypes': course_types
    }


def _empty_summary():
    """Return an empty exam summary."""
    return {
        'total': 0,
        'upcoming': 0,
        'passed': 0,
        'failed': 0,
        'noResult': 0,
        'passRate': 0,
        'atRisk': 0,
        'averageProgress': 0,
        'avgStudyTime': 0,
        'avgStudyTimeFormatted': '0m',
        'avgStudyPassed': 0,
        'avgStudyPassedFormatted': '0m',
        'avgStudyFailed': 0,
        'avgStudyFailedFormatted': '0m',
        'courseTypes': {}
    }


@exam_bp.route('/admin-verify', methods=['POST'])
@login_required
def verify_admin():
    """Verify admin password for full exam data access."""
    data = request.get_json() or {}
    password = data.get('password', '')
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True, 'admin': True})
    return jsonify({'success': False, 'error': 'Invalid password'}), 401


@exam_bp.route('/update-result', methods=['POST'])
@login_required
def update_exam_result():
    """Update pass/fail result for a student (in-memory override)."""
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    result = (data.get('result') or '').upper().strip()
    admin_key = data.get('adminKey', '')

    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400

    if result not in ('PASS', 'FAIL', ''):
        return jsonify({'success': False, 'error': 'Result must be PASS, FAIL, or empty'}), 400

    is_admin = admin_key == ADMIN_PASSWORD

    # Authorization: admin or student must be in user's department
    if not is_admin:
        from routes.dashboard import get_cached_students
        _, formatted_students = get_cached_students(g.department_id, g.absorb_token)
        dept_emails = {(s.get('email') or '').lower().strip() for s in formatted_students}
        if email not in dept_emails:
            return jsonify({'success': False, 'error': 'Not authorized for this student'}), 403

    if result:
        _passfail_overrides[email] = result
        print(f"[EXAM] Pass/fail override set: {email} -> {result}")
    else:
        _passfail_overrides.pop(email, None)
        print(f"[EXAM] Pass/fail override cleared: {email}")

    return jsonify({'success': True, 'email': email, 'result': result})


@exam_bp.route('/update-date', methods=['POST'])
@login_required
def update_exam_date():
    """Update exam date for a student (in-memory override)."""
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    new_date = (data.get('date') or '').strip()  # Expected format: YYYY-MM-DD
    new_time = (data.get('time') or '').strip()  # Optional time like "2:00 PM"
    admin_key = data.get('adminKey', '')

    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400

    if not new_date:
        return jsonify({'success': False, 'error': 'Date required'}), 400

    # Validate date format
    try:
        datetime.strptime(new_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format (expected YYYY-MM-DD)'}), 400

    is_admin = admin_key == ADMIN_PASSWORD

    # Authorization: admin or student must be in user's department
    if not is_admin:
        from routes.dashboard import get_cached_students
        _, formatted_students = get_cached_students(g.department_id, g.absorb_token)
        dept_emails = {(s.get('email') or '').lower().strip() for s in formatted_students}
        if email not in dept_emails:
            return jsonify({'success': False, 'error': 'Not authorized for this student'}), 403

    _exam_date_overrides[email] = {
        'date': new_date,
        'time': new_time
    }
    print(f"[EXAM] Exam date override set: {email} -> {new_date} {new_time}")

    return jsonify({'success': True, 'email': email, 'date': new_date, 'time': new_time})


@exam_bp.route('/record-result', methods=['POST'])
@login_required
def record_exam_result():
    """Record pass/fail with a point-in-time snapshot of student readiness."""
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    result = (data.get('result') or '').upper().strip()
    admin_key = data.get('adminKey', '')
    notes = data.get('notes', '')
    exam_date = data.get('examDate', '')
    exam_state = data.get('examState', '')
    exam_course = data.get('examCourse', '')

    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400
    if result not in ('PASS', 'FAIL'):
        return jsonify({'success': False, 'error': 'Result must be PASS or FAIL'}), 400

    is_admin = admin_key == ADMIN_PASSWORD

    # Authorization
    if not is_admin:
        from routes.dashboard import get_cached_students
        _, formatted_students = get_cached_students(g.department_id, g.absorb_token)
        dept_emails = {(s.get('email') or '').lower().strip() for s in formatted_students}
        if email not in dept_emails:
            return jsonify({'success': False, 'error': 'Not authorized for this student'}), 403

    # Look up the student to get enrollment data for snapshot
    readiness_snapshot = None
    try:
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Try to find student
        student = client.get_user_by_email(email)
        if student:
            user_id = student.get('id') or student.get('Id')
            if user_id:
                enrollments = client.get_user_enrollments(user_id)
                readiness_snapshot = calculate_readiness(enrollments, course_type=exam_course)
    except Exception as e:
        print(f"[EXAM] Could not build readiness snapshot for {email}: {e}")

    # Build the snapshot
    snapshot = {
        'result': result,
        'recordedAt': datetime.utcnow().isoformat(),
        'recordedBy': g.user.get('emailAddress', 'unknown') if hasattr(g, 'user') and g.user else 'unknown',
        'examDate': exam_date,
        'examState': exam_state,
        'examCourse': exam_course,
        'notes': notes,
        'readiness': readiness_snapshot
    }

    # Store snapshot
    if email not in _exam_result_snapshots:
        _exam_result_snapshots[email] = []
    _exam_result_snapshots[email].append(snapshot)

    # Also set the pass/fail override
    _passfail_overrides[email] = result

    print(f"[EXAM] Result recorded: {email} -> {result} (snapshot #{len(_exam_result_snapshots[email])})")

    return jsonify({
        'success': True,
        'email': email,
        'result': result,
        'snapshot': snapshot
    })


@exam_bp.route('/result-snapshots/<email>', methods=['GET'])
@login_required
def get_result_snapshots(email):
    """Get all recorded exam result snapshots for a student."""
    email = email.lower().strip()
    snapshots = _exam_result_snapshots.get(email, [])
    return jsonify({
        'success': True,
        'email': email,
        'snapshots': snapshots
    })


@exam_bp.route('/sync', methods=['POST'])
@login_required
def sync_exam_data():
    """Force refresh exam data from Google Sheet and Absorb lookups."""
    try:
        invalidate_sheet_cache()
        invalidate_exam_absorb_cache()
        sheet_students = fetch_exam_sheet()

        return jsonify({
            'success': True,
            'message': 'Exam data refreshed',
            'count': len(sheet_students)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to sync exam data: {str(e)}'
        }), 500


# --- Study Data Sync to Google Sheet ---

_sync_status = {'running': False, 'progress': 0, 'total': 0, 'message': '', 'error': None}


@exam_bp.route('/sync-study-data', methods=['POST'])
@login_required
def sync_study_data_to_sheet():
    """
    Admin-only: Fetch Absorb data for all sheet students, compute metrics,
    and write results back to Google Sheets.
    """
    global _sync_status

    data = request.get_json() or {}
    admin_key = data.get('adminKey', '')

    if admin_key != ADMIN_PASSWORD:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    if _sync_status['running']:
        return jsonify({'success': False, 'error': 'Sync already in progress'}), 409

    try:
        _sync_status = {'running': True, 'progress': 0, 'total': 0,
                        'message': 'Initializing...', 'error': None}

        # 1. Open the Google Sheet
        _sync_status['message'] = 'Connecting to Google Sheets...'
        from google_sheets_writer import (
            get_worksheet, ensure_sync_columns, find_email_column,
            build_email_to_row_map, write_student_rows_batch
        )
        worksheet = get_worksheet()
        email_col = find_email_column(worksheet)
        sync_col_start = ensure_sync_columns(worksheet)
        email_to_row = build_email_to_row_map(worksheet, email_col)

        emails = list(email_to_row.keys())
        _sync_status['total'] = len(emails)
        _sync_status['message'] = f'Looking up {len(emails)} students in Absorb...'

        # 2. Create API client with admin token
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # 3. Batch look up all students
        found_users = client.get_users_by_emails_batch(emails)
        user_by_email = {}
        for user in found_users:
            ue = (user.get('emailAddress') or user.get('EmailAddress') or '').lower().strip()
            if ue:
                user_by_email[ue] = user

        _sync_status['message'] = f'Found {len(user_by_email)}/{len(emails)} students. Fetching enrollments...'

        # 4. Fetch enrollments in parallel and compute metrics
        rows_to_write = []
        completed = 0

        def process_student(email):
            user = user_by_email.get(email)
            if not user:
                return email, None
            user_id = user.get('id') or user.get('Id')
            if not user_id:
                return email, None
            try:
                enrollments = client.get_user_enrollments(user_id)
                return email, _compute_sync_data(user, enrollments)
            except Exception as e:
                print(f"[SYNC] Error processing {email}: {e}")
                return email, None

        max_workers = min(30, len(user_by_email)) if user_by_email else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_email = {
                executor.submit(process_student, email): email
                for email in emails
            }

            for future in as_completed(future_to_email):
                completed += 1
                _sync_status['progress'] = completed

                email, sync_data = future.result()
                row_number = email_to_row.get(email)
                if sync_data and row_number:
                    rows_to_write.append((row_number, sync_data))

                if completed % 10 == 0 or completed == len(emails):
                    _sync_status['message'] = f'Processed {completed}/{len(emails)} students...'

        # 5. Write all results to Google Sheet in a batch
        _sync_status['message'] = f'Writing {len(rows_to_write)} rows to Google Sheets...'
        if rows_to_write:
            write_student_rows_batch(worksheet, rows_to_write, sync_col_start)

        _sync_status['message'] = 'Sync complete!'
        _sync_status['running'] = False

        # Invalidate caches so next load picks up fresh data
        invalidate_sheet_cache()

        return jsonify({
            'success': True,
            'message': f'Synced {len(rows_to_write)} students to Google Sheets',
            'studentsProcessed': len(emails),
            'studentsWritten': len(rows_to_write),
            'studentsNotFound': len(emails) - len(user_by_email),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        _sync_status['running'] = False
        _sync_status['error'] = str(e)
        return jsonify({
            'success': False,
            'error': f'Sync failed: {str(e)}'
        }), 500


@exam_bp.route('/sync-study-data/status', methods=['GET'])
@login_required
def get_sync_status():
    """Get the current status of a running sync operation."""
    return jsonify({
        'success': True,
        **_sync_status
    })


def _compute_sync_data(user, enrollments):
    """
    Compute all sync column values for a single student.
    Returns a dict keyed by column header names matching SYNC_COLUMNS.
    """
    from utils.readiness import (
        _is_practice_exam, _is_state_law, _is_video_course,
        _is_life_video, _is_health_video, _is_prelicensing,
        _get_enrollment_minutes, _get_enrollment_score,
        _get_enrollment_name, _get_enrollment_status,
        _get_enrollment_progress
    )

    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # Categorize enrollments
    prelicensing_time = 0
    exam_prep_time = 0
    prelicensing_progress_values = []
    exam_prep_progress_values = []
    life_video_time = 0
    health_video_time = 0
    practice_scores = []
    state_law_time = 0
    state_law_completions = 0

    for e in enrollments:
        name = _get_enrollment_name(e)
        minutes = _get_enrollment_minutes(e)
        status = _get_enrollment_status(e)
        progress = _get_enrollment_progress(e)

        if _is_prelicensing(name):
            prelicensing_time += minutes
            prelicensing_progress_values.append(progress)

        # Exam prep: contains 'prep' or 'study' but not practice exam
        if name and ('prep' in name.lower() or 'study' in name.lower()) and not _is_practice_exam(name):
            exam_prep_time += minutes
            exam_prep_progress_values.append(progress)

        if _is_practice_exam(name):
            score = _get_enrollment_score(e)
            practice_scores.append(score)

        if _is_state_law(name):
            state_law_time += minutes
            if status in (2, 3):
                state_law_completions += 1

        if _is_life_video(name):
            life_video_time += minutes
        if _is_health_video(name):
            health_video_time += minutes

    # LMS Total Time: Pre-License + Exam Prep
    lms_total = round(prelicensing_time + exam_prep_time, 1)

    # Progress averages
    pre_license_progress = (
        round(sum(prelicensing_progress_values) / len(prelicensing_progress_values), 1)
        if prelicensing_progress_values else 0
    )
    exam_prep_progress = (
        round(sum(exam_prep_progress_values) / len(exam_prep_progress_values), 1)
        if exam_prep_progress_values else 0
    )

    # Practice exam scores (comma-separated)
    scores_str = ', '.join(str(round(s, 1)) for s in practice_scores)

    # Consecutive passing >= 80%
    consecutive = 0
    for score in practice_scores:
        if score >= 80:
            consecutive += 1
        else:
            break

    # Last login
    last_login = (
        user.get('lastLoginDate') or user.get('LastLoginDate') or
        user.get('dateLastAccessed') or user.get('DateLastAccessed') or ''
    )
    if last_login and isinstance(last_login, str):
        try:
            clean = last_login.replace('Z', '').split('+')[0].split('.')[0]
            dt = datetime.fromisoformat(clean)
            last_login = dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, AttributeError):
            pass

    # Department & Phone
    dept = user.get('departmentName') or user.get('DepartmentName') or ''
    phone = user.get('phone') or user.get('Phone') or ''

    # Gap metrics
    gap = calculate_gap_metrics(enrollments)

    # Readiness
    readiness = calculate_readiness(enrollments)

    return {
        'LMS Total Time (min)': lms_total,
        'Life Video Time (min)': round(life_video_time, 1),
        'Health Video Time (min)': round(health_video_time, 1),
        'Pre-License Progress (%)': pre_license_progress,
        'Exam Prep Progress (%)': exam_prep_progress,
        'Practice Exam Scores': scores_str,
        'Consecutive Passing': consecutive,
        'State Laws Time (min)': round(state_law_time, 1),
        'State Laws Completions': state_law_completions,
        'Last Login': last_login,
        'Department': dept,
        'Phone': phone,
        'Study Gaps': gap['study_gap_count'],
        'Total Gap Days': gap['total_gap_days'],
        'Largest Gap (days)': gap['largest_gap_days'],
        'Last Gap Date': gap['last_gap_date'],
        'Readiness': readiness['status'],
        'Criteria Met': f"{readiness['criteriaMet']}/{readiness['criteriaTotal']}",
        'Last Sync': now_str,
    }
