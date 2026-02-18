"""Dashboard routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g, request
import re
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils import format_student_for_response, get_status_from_last_login
from routes.exam import invalidate_exam_absorb_cache, get_department_name

dashboard_bp = Blueprint('dashboard', __name__)

# Simple in-memory cache for student data (per department)
# Structure: {department_id: {'data': [...], 'timestamp': datetime, 'formatted': [...]}}
_student_cache = {}
CACHE_TTL_MINUTES = 5  # Cache data for 5 minutes


def get_cached_students(department_id, token):
    """Get students from cache or fetch fresh data."""
    now = datetime.utcnow()

    # Check if we have valid cached data
    if department_id in _student_cache:
        cache_entry = _student_cache[department_id]
        cache_age = now - cache_entry['timestamp']

        if cache_age < timedelta(minutes=CACHE_TTL_MINUTES):
            print(f"[CACHE] Using cached data for {department_id} (age: {cache_age.seconds}s)")
            return cache_entry['data'], cache_entry['formatted']

    # Fetch fresh data
    print(f"[CACHE] Fetching fresh data for {department_id}")
    client = AbsorbAPIClient()
    client.set_token(token)
    students = client.get_students_with_progress(department_id)

    # Format students
    formatted_students = [format_student_for_response(student) for student in students]

    # Sort by status priority (re-engage first), then by progress
    formatted_students.sort(
        key=lambda s: (s['status']['priority'], -s['progress']['value']),
        reverse=False
    )

    # Store in cache
    _student_cache[department_id] = {
        'data': students,
        'formatted': formatted_students,
        'timestamp': now
    }

    return students, formatted_students


def invalidate_cache(department_id):
    """Clear cache for a department."""
    if department_id in _student_cache:
        del _student_cache[department_id]
        print(f"[CACHE] Invalidated cache for {department_id}")


def get_quick_students(department_id, token):
    """Get basic student data quickly without enrollments."""
    # Check cache first
    if department_id in _student_cache:
        cache_entry = _student_cache[department_id]
        cache_age = datetime.utcnow() - cache_entry['timestamp']
        if cache_age < timedelta(minutes=CACHE_TTL_MINUTES):
            return cache_entry['formatted']

    # Get basic data only (fast)
    client = AbsorbAPIClient()
    client.set_token(token)
    students = client.get_students_basic(department_id)

    # Format students
    formatted = [format_student_for_response(student) for student in students]
    formatted.sort(key=lambda s: (s['status']['priority'], -s['progress']['value']), reverse=False)
    return formatted


@dashboard_bp.route('/summary/quick', methods=['GET'])
@login_required
def get_summary_quick():
    """
    Get quick summary (just student count and status from basic data).
    """
    try:
        formatted_students = get_quick_students(g.department_id, g.absorb_token)
        total = len(formatted_students)
        complete = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
        active = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
        warning = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
        reengage = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total,
                'completeCount': complete,
                'activeCount': active,
                'warningCount': warning,
                'reengageCount': reengage,
                'averageProgress': 0  # Will be updated with full load
            },
            'quick': True
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/summary', methods=['GET'])
@login_required
def get_summary():
    """
    Get dashboard summary with KPI data (uses cache).

    Returns:
        JSON response with summary statistics
    """
    try:
        # Get students from cache (formatted students have correct COMPLETE status)
        students, formatted_students = get_cached_students(g.department_id, g.absorb_token)

        # Calculate KPIs from formatted students (which have progress-aware status)
        total_students = len(formatted_students)
        complete_count = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
        active_count = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
        warning_count = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
        reengage_count = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')
        total_progress = sum(s['progress']['value'] for s in formatted_students)

        avg_progress = round(total_progress / total_students, 1) if total_students > 0 else 0

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total_students,
                'completeCount': complete_count,
                'activeCount': active_count,
                'warningCount': warning_count,
                'reengageCount': reengage_count,
                'averageProgress': avg_progress
            }
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch dashboard summary'
        }), 500


@dashboard_bp.route('/students/quick', methods=['GET'])
@login_required
def get_students_quick():
    """
    Get students quickly without enrollment data (fast initial load).
    """
    try:
        formatted_students = get_quick_students(g.department_id, g.absorb_token)
        return jsonify({
            'success': True,
            'students': formatted_students,
            'count': len(formatted_students),
            'quick': True
        })
    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch students: {str(e)}'
        }), 500


@dashboard_bp.route('/students', methods=['GET'])
@login_required
def get_students():
    """
    Get all students in the department with progress data (uses cache).

    Returns:
        JSON response with formatted student list
    """
    try:
        # Get students from cache
        _, formatted_students = get_cached_students(g.department_id, g.absorb_token)

        return jsonify({
            'success': True,
            'students': formatted_students,
            'count': len(formatted_students)
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        import traceback
        print(f"[ERROR] Students fetch failed: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to fetch students: {str(e)}'
        }), 500


GUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
MAX_EXTRA_DEPTS = 10


def _compute_summary(formatted_students):
    """Calculate KPI summary dict from a list of formatted students."""
    total = len(formatted_students)
    complete = sum(1 for s in formatted_students if s['status']['status'] == 'COMPLETE')
    active = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
    warning = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
    reengage = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')
    total_progress = sum(s['progress']['value'] for s in formatted_students)
    avg_progress = round(total_progress / total, 1) if total > 0 else 0

    return {
        'totalStudents': total,
        'completeCount': complete,
        'activeCount': active,
        'warningCount': warning,
        'reengageCount': reengage,
        'averageProgress': avg_progress,
    }


def _fetch_dept_students(dept_id, token):
    """Fetch and annotate students for a single department. Returns (dept_meta, formatted_list)."""
    client = AbsorbAPIClient()
    client.set_token(token)
    dept_name = get_department_name(client, dept_id)

    _, formatted = get_cached_students(dept_id, token)

    # Inject departmentName into each student
    for s in formatted:
        s['departmentName'] = dept_name

    return {
        'id': dept_id,
        'name': dept_name,
        'studentCount': len(formatted),
        'status': 'ok',
    }, formatted


@dashboard_bp.route('/students/multi', methods=['GET'])
@login_required
def get_students_multi():
    """Get students from multiple departments, merged into one list."""
    try:
        extra_param = request.args.get('departments', '')
        extra_ids = [d.strip() for d in extra_param.split(',') if d.strip()] if extra_param else []

        # Validate GUIDs and cap at MAX_EXTRA_DEPTS
        valid_ids = []
        dept_meta = []
        for d in extra_ids[:MAX_EXTRA_DEPTS]:
            if GUID_RE.match(d):
                if d.lower() != (g.department_id or '').lower():
                    valid_ids.append(d)
            else:
                dept_meta.append({'id': d, 'name': None, 'studentCount': 0, 'status': 'error', 'error': 'Invalid GUID format'})

        # Always include user's own department
        all_dept_ids = [g.department_id] + valid_ids

        # Fetch all departments in parallel
        all_formatted = []
        with ThreadPoolExecutor(max_workers=min(10, len(all_dept_ids))) as executor:
            future_to_dept = {
                executor.submit(_fetch_dept_students, dept_id, g.absorb_token): dept_id
                for dept_id in all_dept_ids
            }
            for future in as_completed(future_to_dept):
                dept_id = future_to_dept[future]
                try:
                    meta, students = future.result()
                    dept_meta.append(meta)
                    all_formatted.extend(students)
                except Exception as e:
                    print(f"[MULTI-DEPT] Error fetching {dept_id}: {e}")
                    dept_meta.append({
                        'id': dept_id,
                        'name': None,
                        'studentCount': 0,
                        'status': 'error',
                        'error': str(e),
                    })

        # Sort merged list
        all_formatted.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        return jsonify({
            'success': True,
            'students': all_formatted,
            'count': len(all_formatted),
            'summary': _compute_summary(all_formatted),
            'departments': dept_meta,
        })

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        import traceback
        print(f"[ERROR] Multi-dept fetch failed: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Failed to fetch students: {str(e)}'}), 500


@dashboard_bp.route('/sync', methods=['POST'])
@login_required
def sync_data():
    """
    Force sync/refresh data from Absorb LMS (clears cache).
    Accepts optional extraDepartments list in JSON body for multi-dept sync.
    """
    try:
        data = request.get_json(silent=True) or {}
        extra_dept_ids = data.get('extraDepartments', [])

        # Build list of all dept IDs to sync
        all_dept_ids = [g.department_id]
        for d in extra_dept_ids[:MAX_EXTRA_DEPTS]:
            if isinstance(d, str) and GUID_RE.match(d) and d.lower() != (g.department_id or '').lower():
                all_dept_ids.append(d)

        dept_name = g.user.get('departmentName', 'Unknown')
        print(f"[SYNC] Starting sync for {len(all_dept_ids)} department(s): {dept_name} ({g.department_id})")

        # Invalidate caches
        for dept_id in all_dept_ids:
            invalidate_cache(dept_id)
        invalidate_exam_absorb_cache()

        # Fetch all departments (parallel if multiple)
        all_formatted = []
        dept_meta = []

        if len(all_dept_ids) == 1:
            # Single department - original fast path
            meta, formatted = _fetch_dept_students(g.department_id, g.absorb_token)
            dept_meta.append(meta)
            all_formatted = formatted
        else:
            with ThreadPoolExecutor(max_workers=min(10, len(all_dept_ids))) as executor:
                future_to_dept = {
                    executor.submit(_fetch_dept_students, dept_id, g.absorb_token): dept_id
                    for dept_id in all_dept_ids
                }
                for future in as_completed(future_to_dept):
                    dept_id = future_to_dept[future]
                    try:
                        meta, students = future.result()
                        dept_meta.append(meta)
                        all_formatted.extend(students)
                    except Exception as e:
                        print(f"[SYNC] Error fetching {dept_id}: {e}")
                        dept_meta.append({'id': dept_id, 'name': None, 'studentCount': 0, 'status': 'error', 'error': str(e)})

        # Sort
        all_formatted.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        print(f"[SYNC] Got {len(all_formatted)} students across {len(all_dept_ids)} departments")

        return jsonify({
            'success': True,
            'message': 'Data synced successfully',
            'summary': _compute_summary(all_formatted),
            'students': all_formatted,
            'departments': dept_meta,
            'syncedAt': g.user.get('loginTime')
        })

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to sync data'}), 500


@dashboard_bp.route('/export', methods=['GET'])
@login_required
def export_data():
    """
    Export student data as CSV.
    Accepts optional departments query param for multi-dept export.
    """
    from flask import Response
    import csv
    from io import StringIO

    try:
        extra_param = request.args.get('departments', '')
        extra_ids = [d.strip() for d in extra_param.split(',') if d.strip() and GUID_RE.match(d.strip())] if extra_param else []
        multi_dept = len(extra_ids) > 0

        # Build dept list
        all_dept_ids = [g.department_id]
        for d in extra_ids[:MAX_EXTRA_DEPTS]:
            if d.lower() != (g.department_id or '').lower():
                all_dept_ids.append(d)

        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Gather all students
        all_students = []
        for dept_id in all_dept_ids:
            raw, _ = get_cached_students(dept_id, g.absorb_token)
            dept_name = get_department_name(client, dept_id) if multi_dept else ''
            for student in raw:
                student['_dept_name'] = dept_name
            all_students.extend(raw)

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        headers = ['First Name', 'Last Name', 'Email', 'Status', 'Last Login', 'Course', 'Progress (%)', 'Time Spent (minutes)']
        if multi_dept:
            headers.insert(0, 'Department')
        writer.writerow(headers)

        for student in all_students:
            status = get_status_from_last_login(student.get('lastLoginDate'))
            row = [
                student.get('firstName', ''),
                student.get('lastName', ''),
                student.get('emailAddress', ''),
                status['status'],
                student.get('lastLoginDate', 'Never'),
                student.get('courseName', 'No Course'),
                round(student.get('progress', 0), 1),
                student.get('timeSpent', 0)
            ]
            if multi_dept:
                row.insert(0, student.get('_dept_name', ''))
            writer.writerow(row)

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=students_export_{g.department_id[:8]}.csv'
            }
        )

    except AbsorbAPIError as e:
        return jsonify({'success': False, 'error': str(e.message)}), e.status_code or 500
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to export data'}), 500
