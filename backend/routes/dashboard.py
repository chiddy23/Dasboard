"""Dashboard routes for JustInsurance Student Dashboard."""

from flask import Blueprint, jsonify, g
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absorb_api import AbsorbAPIClient, AbsorbAPIError
from middleware import login_required
from utils import format_student_for_response, get_status_from_last_login

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
        active = sum(1 for s in formatted_students if s['status']['status'] == 'ACTIVE')
        warning = sum(1 for s in formatted_students if s['status']['status'] == 'WARNING')
        reengage = sum(1 for s in formatted_students if s['status']['status'] == 'RE-ENGAGE')

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total,
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
        # Get students from cache
        students, _ = get_cached_students(g.department_id, g.absorb_token)

        # Calculate KPIs
        total_students = len(students)
        active_count = 0
        warning_count = 0
        reengage_count = 0
        total_progress = 0

        for student in students:
            status = get_status_from_last_login(student.get('lastLoginDate'))

            if status['status'] == 'ACTIVE':
                active_count += 1
            elif status['status'] == 'WARNING':
                warning_count += 1
            else:
                reengage_count += 1

            total_progress += student.get('progress', 0)

        avg_progress = round(total_progress / total_students, 1) if total_students > 0 else 0

        return jsonify({
            'success': True,
            'summary': {
                'totalStudents': total_students,
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


@dashboard_bp.route('/sync', methods=['POST'])
@login_required
def sync_data():
    """
    Force sync/refresh data from Absorb LMS (clears cache).

    Returns:
        JSON response with fresh data
    """
    try:
        dept_name = g.user.get('departmentName', 'Unknown')
        print(f"[SYNC] Starting sync for department: {dept_name} ({g.department_id})")
        print(f"[SYNC] Token present: {bool(g.absorb_token)}")

        # Invalidate cache to force fresh fetch
        invalidate_cache(g.department_id)

        # Initialize API client with user's token
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Get fresh data
        students = client.get_students_with_progress(g.department_id)
        print(f"[SYNC] Got {len(students)} students")

        # Format students
        formatted_students = [
            format_student_for_response(student)
            for student in students
        ]

        # Calculate summary
        total_students = len(students)
        active_count = 0
        warning_count = 0
        reengage_count = 0
        total_progress = 0

        for student in students:
            status = get_status_from_last_login(student.get('lastLoginDate'))

            if status['status'] == 'ACTIVE':
                active_count += 1
            elif status['status'] == 'WARNING':
                warning_count += 1
            else:
                reengage_count += 1

            total_progress += student.get('progress', 0)

        avg_progress = round(total_progress / total_students, 1) if total_students > 0 else 0

        # Sort students
        formatted_students.sort(
            key=lambda s: (s['status']['priority'], -s['progress']['value']),
            reverse=False
        )

        return jsonify({
            'success': True,
            'message': 'Data synced successfully',
            'summary': {
                'totalStudents': total_students,
                'activeCount': active_count,
                'warningCount': warning_count,
                'reengageCount': reengage_count,
                'averageProgress': avg_progress
            },
            'students': formatted_students,
            'syncedAt': g.user.get('loginTime')
        })

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to sync data'
        }), 500


@dashboard_bp.route('/export', methods=['GET'])
@login_required
def export_data():
    """
    Export student data as CSV.

    Returns:
        CSV file download
    """
    from flask import Response
    import csv
    from io import StringIO

    try:
        # Initialize API client with user's token
        client = AbsorbAPIClient()
        client.set_token(g.absorb_token)

        # Get all students
        students = client.get_students_with_progress(g.department_id)

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            'First Name',
            'Last Name',
            'Email',
            'Status',
            'Last Login',
            'Course',
            'Progress (%)',
            'Time Spent (minutes)'
        ])

        # Data rows
        for student in students:
            status = get_status_from_last_login(student.get('lastLoginDate'))
            writer.writerow([
                student.get('firstName', ''),
                student.get('lastName', ''),
                student.get('emailAddress', ''),
                status['status'],
                student.get('lastLoginDate', 'Never'),
                student.get('courseName', 'No Course'),
                round(student.get('progress', 0), 1),
                student.get('timeSpent', 0)
            ])

        # Create response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=students_export_{g.department_id[:8]}.csv'
            }
        )

    except AbsorbAPIError as e:
        return jsonify({
            'success': False,
            'error': str(e.message)
        }), e.status_code or 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to export data'
        }), 500
