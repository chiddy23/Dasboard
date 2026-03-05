"""Static demo mode: serves pre-captured, anonymized data with zero API calls.

All demo data is loaded from data/demo_snapshot.json on first access.
Personal info is already anonymized in the snapshot. Dates are stored as
offsets and computed at load time so lastLogin stays fresh and exam dates
stay in the future.
"""

import json
import os
from datetime import datetime, timedelta

from utils.formatters import (
    format_student_for_response, format_progress, format_time_spent,
    format_datetime, format_relative_time, parse_absorb_date,
    parse_time_spent_to_minutes, get_enrollment_status_text
)
from utils.readiness import calculate_readiness
from utils.gap_metrics import calculate_gap_metrics

DEMO_DEPT_ID = 'de000000-0000-0000-0000-de0000000001'
DEMO_DEPT_NAME = 'Demo Agency - Dashboard Preview'

_snapshot = None
_student_ids = set()
_student_index = {}  # id -> index in dashboard list
_name_map = {}       # id -> (firstName, lastName, email)


def _load_snapshot():
    """Load demo_snapshot.json, patch date offsets, pre-compute details."""
    global _snapshot, _student_ids, _student_index, _name_map

    path = os.path.join(os.path.dirname(__file__), 'data', 'demo_snapshot.json')
    with open(path, 'r') as f:
        _snapshot = json.load(f)

    now = datetime.utcnow()
    today = now.date()

    # Patch dashboard students: convert _loginDaysAgo to real lastLoginDate
    for i, s in enumerate(_snapshot['dashboard']):
        days_ago = s.pop('_loginDaysAgo', 1)
        s['lastLoginDate'] = (now - timedelta(days=days_ago)).isoformat()

        sid = s['id']
        _student_ids.add(sid)
        _student_index[sid] = i
        _name_map[sid] = (s['firstName'], s['lastName'], s['emailAddress'])

    # Patch exam students: convert _examDayOffset to real dates
    for entry in _snapshot['exam']['students']:
        offset = entry.pop('_examDayOffset', 0)
        exam_date = today + timedelta(days=offset)
        entry['examDate'] = exam_date.strftime('%b %d, %Y')
        entry['examDateRaw'] = exam_date.strftime('%Y-%m-%d')

    # Pre-compute detail data for each dashboard student
    _snapshot['details'] = {}
    for s in _snapshot['dashboard']:
        sid = s['id']
        enrollments = s.get('enrollments', [])

        # Format enrollments for detail modal
        formatted_enrollments = []
        for enrollment in enrollments:
            progress_val = enrollment.get('progress', 0)
            time_spent_val = '0'
            for tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                tv = enrollment.get(tf)
                if tv and parse_time_spent_to_minutes(tv) > 0:
                    time_spent_val = tv
                    break
            status_val = enrollment.get('status', 0)
            course_name = (enrollment.get('name') or enrollment.get('Name')
                           or enrollment.get('courseName') or 'Unknown Course')
            date_enrolled = enrollment.get('dateAdded') or enrollment.get('dateStarted')
            date_completed = enrollment.get('dateCompleted')
            date_last_accessed = (enrollment.get('accessDate')
                                  or enrollment.get('dateEdited')
                                  or enrollment.get('dateStarted'))

            formatted_enrollments.append({
                'id': enrollment.get('id'),
                'courseId': enrollment.get('courseId'),
                'courseName': course_name,
                'progress': format_progress(progress_val),
                'timeSpent': {
                    'minutes': parse_time_spent_to_minutes(time_spent_val),
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
        formatted_enrollments.sort(
            key=lambda e: (0 if e['status'] == 1 else 1, -e['progress']['value'])
        )

        _snapshot['details'][sid] = {
            'formatted_enrollments': formatted_enrollments,
            'totalEnrollments': len(enrollments),
            'completedEnrollments': sum(
                1 for e in enrollments if e.get('status') in [2, 3]
            ),
            'readiness': calculate_readiness(enrollments),
            'gapMetrics': calculate_gap_metrics(enrollments),
        }

    # Enrich exam entries with dashboard data (progress, status, timeSpent, etc.)
    for entry in _snapshot['exam']['students']:
        sid = entry.get('id')
        if sid and sid in _student_index:
            s = _snapshot['dashboard'][_student_index[sid]]
            formatted = format_student_for_response(s)
            # Merge formatted fields into exam entry
            for key in ('status', 'lastLogin', 'progress', 'courseName',
                        'timeSpent', 'examPrepTime', 'phone', 'username',
                        'enrollmentStatus', 'enrollmentStatusText', 'departmentId'):
                entry[key] = formatted.get(key, entry.get(key))
            # Add readiness and gap metrics
            detail = _snapshot['details'].get(sid, {})
            entry['readiness'] = detail.get('readiness')
            entry['gapMetrics'] = detail.get('gapMetrics')
        else:
            # Unmatched student
            entry.setdefault('status', {
                'status': 'UNKNOWN', 'class': 'gray', 'emoji': '', 'priority': 99
            })
            entry.setdefault('lastLogin', {
                'raw': None, 'formatted': 'N/A', 'relative': 'N/A'
            })
            entry.setdefault('progress', {
                'value': 0, 'display': '0%', 'colorClass': 'low', 'color': '#ef4444'
            })
            entry.setdefault('courseName', 'Not in Absorb')
            entry.setdefault('timeSpent', {'minutes': 0, 'formatted': '0m'})
            entry.setdefault('examPrepTime', {'minutes': 0, 'formatted': '0m'})
            entry['departmentName'] = 'Not in Absorb'

    print(f"[DEMO] Loaded static snapshot: {len(_snapshot['dashboard'])} students, "
          f"{len(_snapshot['exam']['students'])} exam entries")


def _ensure_loaded():
    if _snapshot is None:
        _load_snapshot()


# ── Public API ────────────────────────────────────────────────────────

def is_demo_dept(dept_id):
    """Check if a department ID is the demo department."""
    if not dept_id:
        return False
    return dept_id.lower().strip() == DEMO_DEPT_ID.lower()


def is_demo_student(student_id):
    """Check if this is a demo student ID."""
    _ensure_loaded()
    return student_id in _student_ids


def get_demo_name(demo_id):
    """Get fake name info for a demo student. Returns (firstName, lastName, email)."""
    _ensure_loaded()
    return _name_map.get(demo_id, ('Demo', 'Student', 'demo@justinsurance.com'))


def get_demo_email_lookup():
    """Get email -> demo info mapping for exam tab anonymization.

    Returns dict: email -> {firstName, lastName, fullName, email, demoId}
    """
    _ensure_loaded()
    lookup = {}
    for s in _snapshot['dashboard']:
        email = s['emailAddress'].lower()
        lookup[email] = {
            'firstName': s['firstName'],
            'lastName': s['lastName'],
            'fullName': f"{s['firstName']} {s['lastName']}",
            'email': s['emailAddress'],
            'demoId': s['id'],
        }
    return lookup


def get_cached_demo_students():
    """Get demo students from static snapshot. Always returns data, never None."""
    _ensure_loaded()
    return _snapshot['dashboard']


def get_demo_student_detail(demo_id):
    """Get pre-computed detail for a demo student (for the detail modal).

    Returns the full formatted student dict with enrollments, readiness, gapMetrics.
    """
    _ensure_loaded()
    if demo_id not in _student_index:
        return None

    s = _snapshot['dashboard'][_student_index[demo_id]]
    detail = _snapshot['details'][demo_id]

    # Build the formatted student response
    formatted = format_student_for_response(s)
    formatted['enrollments'] = detail['formatted_enrollments']
    formatted['totalEnrollments'] = detail['totalEnrollments']
    formatted['completedEnrollments'] = detail['completedEnrollments']
    formatted['readiness'] = detail['readiness']
    formatted['gapMetrics'] = detail['gapMetrics']
    return formatted


def get_demo_exam_data():
    """Get static exam data (students + summary). Returns dict with 'students' and 'examSummary'."""
    _ensure_loaded()

    students = _snapshot['exam']['students']
    now = datetime.utcnow()

    # Calculate summary from the enriched exam entries
    total = len(students)
    passed_students = [s for s in students if (s.get('passFail') or '').upper() == 'PASS']
    failed_students = [s for s in students if (s.get('passFail') or '').upper() == 'FAIL']
    passed = len(passed_students)
    failed = len(failed_students)

    upcoming = 0
    at_risk = 0
    for s in students:
        exam_raw = s.get('examDateRaw', '')
        try:
            dt = datetime.strptime(exam_raw, '%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        has_result = bool(s.get('passFail', '').strip())
        if dt > now and not has_result:
            upcoming += 1
            if s.get('matched') and s.get('progress', {}).get('value', 0) < 80:
                at_risk += 1

    no_result = total - passed - failed - upcoming
    completed_exams = passed + failed
    pass_rate = round((passed / completed_exams * 100), 1) if completed_exams > 0 else 0

    matched = [s for s in students if s.get('matched')]
    avg_progress = 0
    avg_study_time = 0
    if matched:
        avg_progress = round(
            sum(s['progress']['value'] for s in matched) / len(matched), 1
        )
        total_study = sum(
            (s.get('timeSpent', {}).get('minutes', 0) or 0) +
            (s.get('examPrepTime', {}).get('minutes', 0) or 0)
            for s in matched
        )
        avg_study_time = round(total_study / len(matched))

    def fmt(m):
        return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"

    matched_passed = [s for s in passed_students if s.get('matched')]
    matched_failed = [s for s in failed_students if s.get('matched')]
    avg_passed = 0
    avg_failed = 0
    if matched_passed:
        t = sum((s.get('timeSpent', {}).get('minutes', 0) or 0) +
                (s.get('examPrepTime', {}).get('minutes', 0) or 0)
                for s in matched_passed)
        avg_passed = round(t / len(matched_passed))
    if matched_failed:
        t = sum((s.get('timeSpent', {}).get('minutes', 0) or 0) +
                (s.get('examPrepTime', {}).get('minutes', 0) or 0)
                for s in matched_failed)
        avg_failed = round(t / len(matched_failed))

    course_types = {}
    for s in students:
        c = (s.get('examCourse') or 'Unknown').strip()
        if c not in course_types:
            course_types[c] = {'total': 0, 'passed': 0, 'failed': 0}
        course_types[c]['total'] += 1
        pf = (s.get('passFail') or '').upper()
        if pf == 'PASS':
            course_types[c]['passed'] += 1
        elif pf == 'FAIL':
            course_types[c]['failed'] += 1

    return {
        'students': students,
        'examSummary': {
            'total': total,
            'upcoming': upcoming,
            'passed': passed,
            'failed': failed,
            'noResult': max(0, no_result),
            'passRate': pass_rate,
            'atRisk': at_risk,
            'averageProgress': avg_progress,
            'avgStudyTime': avg_study_time,
            'avgStudyTimeFormatted': fmt(avg_study_time),
            'avgStudyPassed': avg_passed,
            'avgStudyPassedFormatted': fmt(avg_passed),
            'avgStudyFailed': avg_failed,
            'avgStudyFailedFormatted': fmt(avg_failed),
            'courseTypes': course_types,
        }
    }
