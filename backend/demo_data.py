"""Demo data for JustInsurance Student Dashboard.

Provides realistic fake student data for demos/presentations.
When the DEMO_DEPT_ID is used, the dashboard serves this data
instead of calling the Absorb API.
"""

from datetime import datetime, timedelta
import uuid

DEMO_DEPT_ID = 'de000000-0000-0000-0000-de0000000001'
DEMO_DEPT_NAME = 'Demo Agency - Dashboard Preview'

# Generate consistent fake IDs for each demo student
_DEMO_IDS = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f'demo-student-{i}')) for i in range(10)]


def is_demo_dept(dept_id):
    """Check if a department ID is the demo department."""
    return dept_id and dept_id.lower() == DEMO_DEPT_ID.lower()


def is_demo_student(student_id):
    """Check if a student ID belongs to a demo student."""
    return student_id and student_id.lower() in [d.lower() for d in _DEMO_IDS]


def _days_ago(n):
    return (datetime.utcnow() - timedelta(days=n)).strftime('%Y-%m-%dT%H:%M:%S')


def _hours_ago(n):
    return (datetime.utcnow() - timedelta(hours=n)).strftime('%Y-%m-%dT%H:%M:%S')


def get_demo_students():
    """Return (raw_students, formatted_students_not_needed) for the demo department.

    Returns raw student dicts that can be passed to format_student_for_response().
    """
    now = datetime.utcnow()

    students = [
        # 1. Brenda Lopez - Just started, Life & Health, low progress
        {
            'id': _DEMO_IDS[0],
            'firstName': 'Brenda',
            'lastName': 'Lopez',
            'emailAddress': 'brenda.lopez.demo@justinsurance.com',
            'username': 'blopez.demo',
            'phone': '(555) 201-4488',
            'lastLoginDate': _days_ago(2),
            'departmentId': DEMO_DEPT_ID,
            'progress': 12.5,
            'timeSpent': 195,  # 3h 15m
            'examPrepTime': 0,
            'courseName': 'Texas Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 1, 'progress': 12.5, 'timeSpent': 195},
            'enrollments': [
                {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 1, 'progress': 12.5, 'timeSpent': 195, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(8)},
            ],
        },
        # 2. Kayla Ostriche - Active, Life & Health, moderate progress
        {
            'id': _DEMO_IDS[1],
            'firstName': 'Kayla',
            'lastName': 'Ostriche',
            'emailAddress': 'kayla.ostriche.demo@justinsurance.com',
            'username': 'kostriche.demo',
            'phone': '(555) 337-9122',
            'lastLoginDate': _hours_ago(6),
            'departmentId': DEMO_DEPT_ID,
            'progress': 38.2,
            'timeSpent': 720,  # 12h
            'examPrepTime': 45,
            'courseName': 'Florida Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Florida Life & Health Pre-Licensing Course', 'status': 1, 'progress': 38.2, 'timeSpent': 720},
            'enrollments': [
                {'name': 'Florida Life & Health Pre-Licensing Course', 'status': 1, 'progress': 38.2, 'timeSpent': 720, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(18)},
                {'name': 'Florida Life & Health Exam Prep Study Guide', 'status': 1, 'progress': 15.0, 'timeSpent': 45, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(5)},
            ],
        },
        # 3. Erika Valadares - Active, Life & Health, good progress
        {
            'id': _DEMO_IDS[2],
            'firstName': 'Erika',
            'lastName': 'Valadares',
            'emailAddress': 'erika.valadares.demo@justinsurance.com',
            'username': 'evaladares.demo',
            'phone': '(555) 482-7163',
            'lastLoginDate': _hours_ago(3),
            'departmentId': DEMO_DEPT_ID,
            'progress': 64.8,
            'timeSpent': 1350,  # 22h 30m
            'examPrepTime': 180,  # 3h
            'courseName': 'Arizona Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Arizona Life & Health Pre-Licensing Course', 'status': 1, 'progress': 64.8, 'timeSpent': 1350},
            'enrollments': [
                {'name': 'Arizona Life & Health Pre-Licensing Course', 'status': 1, 'progress': 64.8, 'timeSpent': 1350, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(25)},
                {'name': 'Arizona Life & Health Exam Prep Study Guide', 'status': 1, 'progress': 40.0, 'timeSpent': 180, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(10)},
                {'name': 'Arizona Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 55, 'score': 72, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(4)},
                {'name': 'Arizona Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 81, 'dateCompleted': _days_ago(2), 'dateStarted': _days_ago(2)},
                {'name': 'Arizona State Law - Life', 'status': 1, 'progress': 60, 'timeSpent': 45, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(6)},
                {'name': 'Life Insurance Video Training', 'status': 1, 'progress': 80, 'timeSpent': 35, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(7)},
            ],
        },
        # 4. Xaviel Diaz - COMPLETE, Life only, passed
        {
            'id': _DEMO_IDS[3],
            'firstName': 'Xaviel',
            'lastName': 'Diaz',
            'emailAddress': 'xaviel.diaz.demo@justinsurance.com',
            'username': 'xdiaz.demo',
            'phone': '(555) 618-3390',
            'lastLoginDate': _days_ago(1),
            'departmentId': DEMO_DEPT_ID,
            'progress': 100,
            'timeSpent': 1440,  # 24h
            'examPrepTime': 320,
            'courseName': 'Texas Life Pre-Licensing Course',
            'enrollmentStatus': 2,
            'primaryEnrollment': {'name': 'Texas Life Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 1440},
            'enrollments': [
                {'name': 'Texas Life Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 1440, 'score': None, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(30)},
                {'name': 'Texas Life Exam Prep Study Guide', 'status': 2, 'progress': 100, 'timeSpent': 320, 'score': None, 'dateCompleted': _days_ago(2), 'dateStarted': _days_ago(15)},
                {'name': 'Texas Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 52, 'score': 78, 'dateCompleted': _days_ago(8), 'dateStarted': _days_ago(8)},
                {'name': 'Texas Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 45, 'score': 85, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(6)},
                {'name': 'Texas Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': 88, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(4)},
                {'name': 'Texas Life Practice Exam v4', 'status': 2, 'progress': 100, 'timeSpent': 38, 'score': 92, 'dateCompleted': _days_ago(2), 'dateStarted': _days_ago(2)},
                {'name': 'Texas State Law - Life', 'status': 2, 'progress': 100, 'timeSpent': 108, 'score': None, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(12)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': None, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(14)},
            ],
        },
        # 5. Catherine Harper - Warning, Life & Health, barely started
        {
            'id': _DEMO_IDS[4],
            'firstName': 'Catherine',
            'lastName': 'Harper',
            'emailAddress': 'catherine.harper.demo@justinsurance.com',
            'username': 'charper.demo',
            'phone': '(555) 745-2001',
            'lastLoginDate': _days_ago(5),
            'departmentId': DEMO_DEPT_ID,
            'progress': 6.3,
            'timeSpent': 110,  # 1h 50m
            'examPrepTime': 0,
            'courseName': 'Georgia Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Georgia Life & Health Pre-Licensing Course', 'status': 1, 'progress': 6.3, 'timeSpent': 110},
            'enrollments': [
                {'name': 'Georgia Life & Health Pre-Licensing Course', 'status': 1, 'progress': 6.3, 'timeSpent': 110, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(14)},
            ],
        },
        # 6. Eric Richard - Active, Health only, mid progress
        {
            'id': _DEMO_IDS[5],
            'firstName': 'Eric',
            'lastName': 'Richard',
            'emailAddress': 'eric.richard.demo@justinsurance.com',
            'username': 'erichard.demo',
            'phone': '(555) 503-8847',
            'lastLoginDate': _hours_ago(12),
            'departmentId': DEMO_DEPT_ID,
            'progress': 55.1,
            'timeSpent': 900,  # 15h
            'examPrepTime': 95,
            'courseName': 'California Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'California Health Pre-Licensing Course', 'status': 1, 'progress': 55.1, 'timeSpent': 900},
            'enrollments': [
                {'name': 'California Health Pre-Licensing Course', 'status': 1, 'progress': 55.1, 'timeSpent': 900, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(20)},
                {'name': 'California Health Exam Prep Study Guide', 'status': 1, 'progress': 25.0, 'timeSpent': 95, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(8)},
                {'name': 'California Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 50, 'score': 68, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(3)},
                {'name': 'California State Law - Health', 'status': 1, 'progress': 40, 'timeSpent': 35, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(5)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 38, 'score': None, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(10)},
            ],
        },
        # 7. Nichole Vassey - COMPLETE, Life & Health, passed
        {
            'id': _DEMO_IDS[6],
            'firstName': 'Nichole',
            'lastName': 'Vassey',
            'emailAddress': 'nichole.vassey.demo@justinsurance.com',
            'username': 'nvassey.demo',
            'phone': '(555) 892-4156',
            'lastLoginDate': _days_ago(2),
            'departmentId': DEMO_DEPT_ID,
            'progress': 100,
            'timeSpent': 2100,  # 35h
            'examPrepTime': 410,
            'courseName': 'Texas Life & Health Pre-Licensing Course',
            'enrollmentStatus': 2,
            'primaryEnrollment': {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2100},
            'enrollments': [
                {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2100, 'score': None, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(42)},
                {'name': 'Texas Life & Health Exam Prep Study Guide', 'status': 2, 'progress': 100, 'timeSpent': 410, 'score': None, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(20)},
                {'name': 'Texas Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 55, 'score': 82, 'dateCompleted': _days_ago(12), 'dateStarted': _days_ago(12)},
                {'name': 'Texas Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 86, 'dateCompleted': _days_ago(9), 'dateStarted': _days_ago(9)},
                {'name': 'Texas Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': 90, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(6)},
                {'name': 'Texas Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 50, 'score': 84, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(5)},
                {'name': 'Texas State Law - Life & Health', 'status': 2, 'progress': 100, 'timeSpent': 115, 'score': None, 'dateCompleted': _days_ago(8), 'dateStarted': _days_ago(18)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': None, 'dateCompleted': _days_ago(15), 'dateStarted': _days_ago(22)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 38, 'score': None, 'dateCompleted': _days_ago(14), 'dateStarted': _days_ago(21)},
            ],
        },
        # 8. Sydney L Schaffer - Active, Life only, high progress
        {
            'id': _DEMO_IDS[7],
            'firstName': 'Sydney',
            'lastName': 'Schaffer',
            'emailAddress': 'sydney.schaffer.demo@justinsurance.com',
            'username': 'sschaffer.demo',
            'phone': '(555) 264-7738',
            'lastLoginDate': _hours_ago(1),
            'departmentId': DEMO_DEPT_ID,
            'progress': 82.4,
            'timeSpent': 1080,  # 18h
            'examPrepTime': 210,
            'courseName': 'South Dakota Life Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'South Dakota Life Pre-Licensing Course', 'status': 1, 'progress': 82.4, 'timeSpent': 1080},
            'enrollments': [
                {'name': 'South Dakota Life Pre-Licensing Course', 'status': 1, 'progress': 82.4, 'timeSpent': 1080, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(22)},
                {'name': 'South Dakota Life Exam Prep Study Guide', 'status': 1, 'progress': 60.0, 'timeSpent': 210, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(12)},
                {'name': 'South Dakota Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 52, 'score': 76, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(7)},
                {'name': 'South Dakota Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 45, 'score': 83, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(4)},
                {'name': 'South Dakota Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': 87, 'dateCompleted': _days_ago(1), 'dateStarted': _days_ago(1)},
                {'name': 'South Dakota State Law - Life', 'status': 2, 'progress': 100, 'timeSpent': 98, 'score': None, 'dateCompleted': _days_ago(9), 'dateStarted': _days_ago(15)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 36, 'score': None, 'dateCompleted': _days_ago(10), 'dateStarted': _days_ago(16)},
            ],
        },
        # 9. Stephanie Goodman - COMPLETE, Life & Health, passed
        {
            'id': _DEMO_IDS[8],
            'firstName': 'Stephanie',
            'lastName': 'Goodman',
            'emailAddress': 'stephanie.goodman.demo@justinsurance.com',
            'username': 'sgoodman.demo',
            'phone': '(555) 171-5529',
            'lastLoginDate': _days_ago(3),
            'departmentId': DEMO_DEPT_ID,
            'progress': 100,
            'timeSpent': 1920,  # 32h
            'examPrepTime': 380,
            'courseName': 'Florida Life & Health Pre-Licensing Course',
            'enrollmentStatus': 2,
            'primaryEnrollment': {'name': 'Florida Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 1920},
            'enrollments': [
                {'name': 'Florida Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 1920, 'score': None, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(38)},
                {'name': 'Florida Life & Health Exam Prep Study Guide', 'status': 2, 'progress': 100, 'timeSpent': 380, 'score': None, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(22)},
                {'name': 'Florida Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 50, 'score': 80, 'dateCompleted': _days_ago(14), 'dateStarted': _days_ago(14)},
                {'name': 'Florida Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 46, 'score': 84, 'dateCompleted': _days_ago(11), 'dateStarted': _days_ago(11)},
                {'name': 'Florida Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': 88, 'dateCompleted': _days_ago(8), 'dateStarted': _days_ago(8)},
                {'name': 'Florida Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 82, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(7)},
                {'name': 'Florida State Law - Life & Health', 'status': 2, 'progress': 100, 'timeSpent': 105, 'score': None, 'dateCompleted': _days_ago(10), 'dateStarted': _days_ago(20)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': None, 'dateCompleted': _days_ago(18), 'dateStarted': _days_ago(25)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': None, 'dateCompleted': _days_ago(17), 'dateStarted': _days_ago(24)},
            ],
        },
        # 10. Oscar Ortega - Re-engage, Life & Health, stalled
        {
            'id': _DEMO_IDS[9],
            'firstName': 'Oscar',
            'lastName': 'Ortega',
            'emailAddress': 'oscar.ortega.demo@justinsurance.com',
            'username': 'oortega.demo',
            'phone': '(555) 639-0074',
            'lastLoginDate': _days_ago(12),
            'departmentId': DEMO_DEPT_ID,
            'progress': 41.7,
            'timeSpent': 840,  # 14h
            'examPrepTime': 60,
            'courseName': 'North Carolina Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'North Carolina Life & Health Pre-Licensing Course', 'status': 1, 'progress': 41.7, 'timeSpent': 840},
            'enrollments': [
                {'name': 'North Carolina Life & Health Pre-Licensing Course', 'status': 1, 'progress': 41.7, 'timeSpent': 840, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(35)},
                {'name': 'North Carolina Life & Health Exam Prep Study Guide', 'status': 1, 'progress': 10.0, 'timeSpent': 60, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(15)},
                {'name': 'North Carolina Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 55, 'score': 62, 'dateCompleted': _days_ago(13), 'dateStarted': _days_ago(13)},
            ],
        },
    ]

    return students


def get_demo_student_detail(student_id):
    """Get a single demo student's full data by ID (for the student detail modal)."""
    for s in get_demo_students():
        if s['id'].lower() == student_id.lower():
            return s
    return None
