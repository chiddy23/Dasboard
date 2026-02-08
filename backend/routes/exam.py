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

        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Remove emails already processed in the Absorb cache (if valid)
        if is_exam_absorb_cache_valid():
            cached_emails = unmatched_emails & set(_exam_absorb_cache.keys())
            emails_to_lookup = unmatched_emails - cached_emails
            print(f"[EXAM] {len(matched_emails)} dept-matched, {len(cached_emails)} cached, {len(emails_to_lookup)} to look up")
        else:
            emails_to_lookup = unmatched_emails
            print(f"[EXAM] {len(matched_emails)} dept-matched, {len(emails_to_lookup)} to look up (cache expired)")

        # 5. Parallel email lookup for unmatched students (search by name + match by email)
        if emails_to_lookup:
            global _exam_absorb_timestamp
            print(f"[EXAM] Looking up {len(emails_to_lookup)} students by name/email...")

            # Build email -> name map from sheet data for name-based search
            email_to_name = {s['email']: s['name'] for s in sheet_students}

            max_workers = min(50, len(emails_to_lookup))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_email = {
                    executor.submit(client.lookup_and_process_student, email, email_to_name.get(email, '')): email
                    for email in emails_to_lookup
                }

                completed = 0
                found = 0
                for future in as_completed(future_to_email):
                    completed += 1
                    email = future_to_email[future]
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

                    if completed % 20 == 0 or completed == len(emails_to_lookup):
                        print(f"[EXAM] Processed {completed}/{len(emails_to_lookup)} lookups ({found} found)")

            _exam_absorb_timestamp = datetime.utcnow()
            print(f"[EXAM] Lookup complete: {found}/{len(emails_to_lookup)} found")

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

                exam_entry = _build_exam_entry(formatted, sheet_student, dept_name, True)
            elif email in _exam_absorb_cache and _exam_absorb_cache[email] is not None:
                # Found via cross-department lookup
                cached = _exam_absorb_cache[email]
                dept_id = cached['raw'].get('departmentId') or ''
                dept_name = get_department_name(client, dept_id) if dept_id else 'Unknown'

                exam_entry = _build_exam_entry(cached['formatted'], sheet_student, dept_name, True)
            else:
                # Not found in Absorb at all
                exam_entry = _build_unmatched_entry(sheet_student)

            # Apply any pass/fail overrides
            if email in _passfail_overrides:
                exam_entry['passFail'] = _passfail_overrides[email]

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


def _build_exam_entry(formatted, sheet_student, dept_name, matched):
    """Build an exam entry from formatted Absorb data + sheet data."""
    return {
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
        'courseName': sheet_student['course'] or 'N/A',
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
        'departmentName': sheet_student.get('agencyOwner') or 'N/A',
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
