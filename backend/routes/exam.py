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
from google_sheets import fetch_exam_sheet, invalidate_sheet_cache, parse_exam_date_for_sort, update_sheet_passfail, update_sheet_exam_date, update_sheet_contact
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

# Load persistent overrides from SQLite into memory (survives restarts)
def _load_overrides():
    """Load saved overrides from SQLite into in-memory dicts."""
    global _passfail_overrides, _exam_date_overrides
    try:
        from snapshot_db import get_all_overrides
        overrides = get_all_overrides()
        for email, row in overrides.items():
            if row.get('pass_fail'):
                _passfail_overrides[email] = row['pass_fail']
            if row.get('exam_date'):
                _exam_date_overrides[email] = {
                    'date': row['exam_date'],
                    'time': row.get('exam_time', '')
                }
        print(f"[EXAM] Loaded {len(_passfail_overrides)} pass/fail and {len(_exam_date_overrides)} date overrides from DB")
    except Exception as e:
        print(f"[EXAM] Failed to load overrides from DB: {e}")

_passfail_overrides = {}
_exam_date_overrides = {}
_exam_result_snapshots = {}
_load_overrides()


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
    else:
        _passfail_overrides.pop(email, None)

    # Persist to SQLite
    from snapshot_db import set_override
    set_override(email, pass_fail=result)
    print(f"[EXAM] Pass/fail override saved: {email} -> {result or '(cleared)'}")

    # Write back to Google Sheet (non-blocking, non-fatal)
    if result:
        update_sheet_passfail(email, result)

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

    # Persist to SQLite
    from snapshot_db import set_override
    set_override(email, exam_date=new_date, exam_time=new_time)
    print(f"[EXAM] Exam date override saved: {email} -> {new_date} {new_time}")

    # Write back to Google Sheet (non-blocking, non-fatal)
    update_sheet_exam_date(email, new_date, new_time)

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

    # Also set the pass/fail override and persist to SQLite
    _passfail_overrides[email] = result
    from snapshot_db import set_override
    set_override(email, pass_fail=result)

    # Write back to Google Sheet (non-blocking, non-fatal)
    update_sheet_passfail(email, result)

    print(f"[EXAM] Result recorded and saved: {email} -> {result}")

    return jsonify({
        'success': True,
        'email': email,
        'result': result,
        'snapshot': snapshot
    })


@exam_bp.route('/update-contact', methods=['POST'])
@login_required
def update_exam_contact():
    """Update student contact info (name, email, phone) in the Google Sheet. Admin only."""
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    admin_key = data.get('adminKey', '')
    new_name = (data.get('name') or '').strip()
    new_email = (data.get('newEmail') or '').strip()
    new_phone = (data.get('phone') or '').strip()

    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400
    if admin_key != ADMIN_PASSWORD:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    if not new_name and not new_email and not new_phone:
        return jsonify({'success': False, 'error': 'No fields to update'}), 400

    update_sheet_contact(email, name=new_name, new_email=new_email, phone=new_phone)

    return jsonify({
        'success': True,
        'email': email,
        'name': new_name,
        'newEmail': new_email,
        'phone': new_phone
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


@exam_bp.route('/snapshots/<email>', methods=['GET'])
@login_required
def get_student_snapshots(email):
    """Get historical study snapshots for a student."""
    from snapshot_db import get_snapshots
    email = email.lower().strip()
    limit = request.args.get('limit', 50, type=int)
    snapshots = get_snapshots(email, limit=limit)
    return jsonify({
        'success': True,
        'email': email,
        'snapshots': snapshots
    })


@exam_bp.route('/sync-scheduler/status', methods=['GET'])
@login_required
def get_scheduler_status():
    """Get the background sync scheduler status."""
    from sync_scheduler import get_scheduler_info
    return jsonify({
        'success': True,
        'scheduler': get_scheduler_info()
    })


