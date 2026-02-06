"""Exam scheduling routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from google_sheets import fetch_exam_sheet, invalidate_sheet_cache, parse_exam_date_for_sort

exam_bp = Blueprint('exam', __name__)

# Cache for department names (departmentId -> name)
_dept_name_cache = {}


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


@exam_bp.route('/students', methods=['GET'])
@login_required
def get_exam_students():
    """Get exam-scheduled students matched with their Absorb data."""
    try:
        # 1. Fetch Google Sheet data
        sheet_students = fetch_exam_sheet()

        if not sheet_students:
            return jsonify({
                'success': True,
                'students': [],
                'count': 0
            })

        # 2. Get cached Absorb students for matching
        from routes.dashboard import get_cached_students
        raw_students, formatted_students = get_cached_students(
            g.department_id, g.absorb_token
        )

        # 3. Build email -> student maps (raw for departmentId, formatted for display)
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

        # 4. Set up Absorb client for department name lookups
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # 5. Match sheet students with Absorb data and combine
        exam_students = []

        for sheet_student in sheet_students:
            email = sheet_student['email']

            formatted = formatted_email_map.get(email)
            raw = raw_email_map.get(email)

            if formatted and raw:
                # Found in Absorb - combine data
                dept_id = raw.get('departmentId') or ''
                dept_name = get_department_name(client, dept_id) if dept_id else g.user.get('departmentName', 'Unknown')

                exam_entry = {
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
                    'matched': True
                }
            else:
                # Not found in Absorb - show sheet data only
                exam_entry = {
                    'id': None,
                    'fullName': sheet_student['name'],
                    'email': email,
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
                    'departmentName': 'Not in department',
                    'matched': False
                }

            exam_students.append(exam_entry)

        # Sort by exam date (upcoming first, then past)
        now = datetime.utcnow()

        def sort_key(s):
            dt = parse_exam_date_for_sort(s.get('examDateRaw', ''))
            # Upcoming exams first (sorted ascending), then past exams (sorted descending)
            is_past = dt < now if dt != datetime.min else True
            return (is_past, dt if not is_past else datetime.max - dt)

        exam_students.sort(key=sort_key)

        return jsonify({
            'success': True,
            'students': exam_students,
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


@exam_bp.route('/sync', methods=['POST'])
@login_required
def sync_exam_data():
    """Force refresh exam data from Google Sheet."""
    try:
        invalidate_sheet_cache()
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
