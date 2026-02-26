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
_DEMO_IDS = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f'demo-student-{i}')) for i in range(20)]


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
        # 11. Marcus Williams - Active, Life & Health, steady progress
        {
            'id': _DEMO_IDS[10],
            'firstName': 'Marcus',
            'lastName': 'Williams',
            'emailAddress': 'marcus.williams.demo@justinsurance.com',
            'username': 'mwilliams.demo',
            'phone': '(555) 413-6682',
            'lastLoginDate': _hours_ago(4),
            'departmentId': DEMO_DEPT_ID,
            'progress': 71.3,
            'timeSpent': 1560,  # 26h
            'examPrepTime': 240,
            'courseName': 'Texas Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 1, 'progress': 71.3, 'timeSpent': 1560},
            'enrollments': [
                {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 1, 'progress': 71.3, 'timeSpent': 1560, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(28)},
                {'name': 'Texas Life & Health Exam Prep Study Guide', 'status': 1, 'progress': 50.0, 'timeSpent': 240, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(14)},
                {'name': 'Texas Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 50, 'score': 74, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(6)},
                {'name': 'Texas Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 47, 'score': 82, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(3)},
                {'name': 'Texas State Law - Life & Health', 'status': 1, 'progress': 70, 'timeSpent': 65, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(10)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 38, 'score': None, 'dateCompleted': _days_ago(12), 'dateStarted': _days_ago(18)},
                {'name': 'Health Insurance Video Training', 'status': 1, 'progress': 60, 'timeSpent': 22, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(8)},
            ],
        },
        # 12. Diana Reyes - COMPLETE, Life & Health, strong finisher
        {
            'id': _DEMO_IDS[11],
            'firstName': 'Diana',
            'lastName': 'Reyes',
            'emailAddress': 'diana.reyes.demo@justinsurance.com',
            'username': 'dreyes.demo',
            'phone': '(555) 558-1204',
            'lastLoginDate': _days_ago(4),
            'departmentId': DEMO_DEPT_ID,
            'progress': 100,
            'timeSpent': 2040,  # 34h
            'examPrepTime': 450,
            'courseName': 'Arizona Life & Health Pre-Licensing Course',
            'enrollmentStatus': 2,
            'primaryEnrollment': {'name': 'Arizona Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2040},
            'enrollments': [
                {'name': 'Arizona Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2040, 'score': None, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(40)},
                {'name': 'Arizona Life & Health Exam Prep Study Guide', 'status': 2, 'progress': 100, 'timeSpent': 450, 'score': None, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(18)},
                {'name': 'Arizona Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 52, 'score': 85, 'dateCompleted': _days_ago(10), 'dateStarted': _days_ago(10)},
                {'name': 'Arizona Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 44, 'score': 89, 'dateCompleted': _days_ago(8), 'dateStarted': _days_ago(8)},
                {'name': 'Arizona Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': 93, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(5)},
                {'name': 'Arizona Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 86, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(4)},
                {'name': 'Arizona State Law - Life & Health', 'status': 2, 'progress': 100, 'timeSpent': 112, 'score': None, 'dateCompleted': _days_ago(9), 'dateStarted': _days_ago(16)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 44, 'score': None, 'dateCompleted': _days_ago(15), 'dateStarted': _days_ago(20)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': None, 'dateCompleted': _days_ago(14), 'dateStarted': _days_ago(19)},
            ],
        },
        # 13. Tyler Bennett - Active, Life only, early-mid progress
        {
            'id': _DEMO_IDS[12],
            'firstName': 'Tyler',
            'lastName': 'Bennett',
            'emailAddress': 'tyler.bennett.demo@justinsurance.com',
            'username': 'tbennett.demo',
            'phone': '(555) 827-3359',
            'lastLoginDate': _hours_ago(8),
            'departmentId': DEMO_DEPT_ID,
            'progress': 28.9,
            'timeSpent': 540,  # 9h
            'examPrepTime': 30,
            'courseName': 'Oklahoma Life Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Oklahoma Life Pre-Licensing Course', 'status': 1, 'progress': 28.9, 'timeSpent': 540},
            'enrollments': [
                {'name': 'Oklahoma Life Pre-Licensing Course', 'status': 1, 'progress': 28.9, 'timeSpent': 540, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(16)},
                {'name': 'Oklahoma Life Exam Prep Study Guide', 'status': 1, 'progress': 8.0, 'timeSpent': 30, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(4)},
            ],
        },
        # 14. Rachel Kim - Warning, Life & Health, hasn't logged in recently
        {
            'id': _DEMO_IDS[13],
            'firstName': 'Rachel',
            'lastName': 'Kim',
            'emailAddress': 'rachel.kim.demo@justinsurance.com',
            'username': 'rkim.demo',
            'phone': '(555) 944-7710',
            'lastLoginDate': _days_ago(6),
            'departmentId': DEMO_DEPT_ID,
            'progress': 47.5,
            'timeSpent': 1020,  # 17h
            'examPrepTime': 120,
            'courseName': 'Georgia Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Georgia Life & Health Pre-Licensing Course', 'status': 1, 'progress': 47.5, 'timeSpent': 1020},
            'enrollments': [
                {'name': 'Georgia Life & Health Pre-Licensing Course', 'status': 1, 'progress': 47.5, 'timeSpent': 1020, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(24)},
                {'name': 'Georgia Life & Health Exam Prep Study Guide', 'status': 1, 'progress': 20.0, 'timeSpent': 120, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(10)},
                {'name': 'Georgia Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 54, 'score': 70, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(7)},
                {'name': 'Georgia State Law - Life & Health', 'status': 1, 'progress': 30, 'timeSpent': 28, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(9)},
            ],
        },
        # 15. Jason Patel - Active, Health only, almost done
        {
            'id': _DEMO_IDS[14],
            'firstName': 'Jason',
            'lastName': 'Patel',
            'emailAddress': 'jason.patel.demo@justinsurance.com',
            'username': 'jpatel.demo',
            'phone': '(555) 316-0093',
            'lastLoginDate': _hours_ago(2),
            'departmentId': DEMO_DEPT_ID,
            'progress': 91.6,
            'timeSpent': 1140,  # 19h
            'examPrepTime': 290,
            'courseName': 'Florida Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Florida Health Pre-Licensing Course', 'status': 1, 'progress': 91.6, 'timeSpent': 1140},
            'enrollments': [
                {'name': 'Florida Health Pre-Licensing Course', 'status': 1, 'progress': 91.6, 'timeSpent': 1140, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(19)},
                {'name': 'Florida Health Exam Prep Study Guide', 'status': 1, 'progress': 75.0, 'timeSpent': 290, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(11)},
                {'name': 'Florida Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 77, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(5)},
                {'name': 'Florida Health Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 44, 'score': 84, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(3)},
                {'name': 'Florida Health Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': 88, 'dateCompleted': _days_ago(1), 'dateStarted': _days_ago(1)},
                {'name': 'Florida State Law - Health', 'status': 2, 'progress': 100, 'timeSpent': 95, 'score': None, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(12)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 40, 'score': None, 'dateCompleted': _days_ago(8), 'dateStarted': _days_ago(14)},
            ],
        },
        # 16. Amanda Torres - Abandoned, Life & Health, no activity in weeks
        {
            'id': _DEMO_IDS[15],
            'firstName': 'Amanda',
            'lastName': 'Torres',
            'emailAddress': 'amanda.torres.demo@justinsurance.com',
            'username': 'atorres.demo',
            'phone': '(555) 702-8831',
            'lastLoginDate': _days_ago(22),
            'departmentId': DEMO_DEPT_ID,
            'progress': 18.4,
            'timeSpent': 360,  # 6h
            'examPrepTime': 0,
            'courseName': 'California Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'California Life & Health Pre-Licensing Course', 'status': 1, 'progress': 18.4, 'timeSpent': 360},
            'enrollments': [
                {'name': 'California Life & Health Pre-Licensing Course', 'status': 1, 'progress': 18.4, 'timeSpent': 360, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(45)},
            ],
        },
        # 17. Jordan Mitchell - Active, Life only, mid progress, improving scores
        {
            'id': _DEMO_IDS[16],
            'firstName': 'Jordan',
            'lastName': 'Mitchell',
            'emailAddress': 'jordan.mitchell.demo@justinsurance.com',
            'username': 'jmitchell.demo',
            'phone': '(555) 589-4427',
            'lastLoginDate': _hours_ago(5),
            'departmentId': DEMO_DEPT_ID,
            'progress': 58.7,
            'timeSpent': 780,  # 13h
            'examPrepTime': 150,
            'courseName': 'Texas Life Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'Texas Life Pre-Licensing Course', 'status': 1, 'progress': 58.7, 'timeSpent': 780},
            'enrollments': [
                {'name': 'Texas Life Pre-Licensing Course', 'status': 1, 'progress': 58.7, 'timeSpent': 780, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(20)},
                {'name': 'Texas Life Exam Prep Study Guide', 'status': 1, 'progress': 35.0, 'timeSpent': 150, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(9)},
                {'name': 'Texas Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 55, 'score': 65, 'dateCompleted': _days_ago(5), 'dateStarted': _days_ago(5)},
                {'name': 'Texas Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 74, 'dateCompleted': _days_ago(2), 'dateStarted': _days_ago(2)},
                {'name': 'Texas State Law - Life', 'status': 1, 'progress': 50, 'timeSpent': 48, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(7)},
                {'name': 'Life Insurance Video Training', 'status': 1, 'progress': 70, 'timeSpent': 28, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(11)},
            ],
        },
        # 18. Lisa Chen - COMPLETE, Life & Health, top performer
        {
            'id': _DEMO_IDS[17],
            'firstName': 'Lisa',
            'lastName': 'Chen',
            'emailAddress': 'lisa.chen.demo@justinsurance.com',
            'username': 'lchen.demo',
            'phone': '(555) 231-5568',
            'lastLoginDate': _days_ago(1),
            'departmentId': DEMO_DEPT_ID,
            'progress': 100,
            'timeSpent': 2280,  # 38h
            'examPrepTime': 520,
            'courseName': 'Texas Life & Health Pre-Licensing Course',
            'enrollmentStatus': 2,
            'primaryEnrollment': {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2280},
            'enrollments': [
                {'name': 'Texas Life & Health Pre-Licensing Course', 'status': 2, 'progress': 100, 'timeSpent': 2280, 'score': None, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(36)},
                {'name': 'Texas Life & Health Exam Prep Study Guide', 'status': 2, 'progress': 100, 'timeSpent': 520, 'score': None, 'dateCompleted': _days_ago(2), 'dateStarted': _days_ago(16)},
                {'name': 'Texas Life Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 48, 'score': 88, 'dateCompleted': _days_ago(10), 'dateStarted': _days_ago(10)},
                {'name': 'Texas Life Practice Exam v2', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': 92, 'dateCompleted': _days_ago(7), 'dateStarted': _days_ago(7)},
                {'name': 'Texas Life Practice Exam v3', 'status': 2, 'progress': 100, 'timeSpent': 38, 'score': 95, 'dateCompleted': _days_ago(4), 'dateStarted': _days_ago(4)},
                {'name': 'Texas Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 45, 'score': 90, 'dateCompleted': _days_ago(3), 'dateStarted': _days_ago(3)},
                {'name': 'Texas State Law - Life & Health', 'status': 2, 'progress': 100, 'timeSpent': 120, 'score': None, 'dateCompleted': _days_ago(6), 'dateStarted': _days_ago(14)},
                {'name': 'Life Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 45, 'score': None, 'dateCompleted': _days_ago(12), 'dateStarted': _days_ago(18)},
                {'name': 'Health Insurance Video Training', 'status': 2, 'progress': 100, 'timeSpent': 42, 'score': None, 'dateCompleted': _days_ago(11), 'dateStarted': _days_ago(17)},
            ],
        },
        # 19. Derek Nguyen - Active, Life & Health, new but motivated
        {
            'id': _DEMO_IDS[18],
            'firstName': 'Derek',
            'lastName': 'Nguyen',
            'emailAddress': 'derek.nguyen.demo@justinsurance.com',
            'username': 'dnguyen.demo',
            'phone': '(555) 478-9936',
            'lastLoginDate': _hours_ago(1),
            'departmentId': DEMO_DEPT_ID,
            'progress': 22.1,
            'timeSpent': 480,  # 8h
            'examPrepTime': 0,
            'courseName': 'South Dakota Life & Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'South Dakota Life & Health Pre-Licensing Course', 'status': 1, 'progress': 22.1, 'timeSpent': 480},
            'enrollments': [
                {'name': 'South Dakota Life & Health Pre-Licensing Course', 'status': 1, 'progress': 22.1, 'timeSpent': 480, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(6)},
            ],
        },
        # 20. Megan Sullivan - Re-engage, Health only, fell off
        {
            'id': _DEMO_IDS[19],
            'firstName': 'Megan',
            'lastName': 'Sullivan',
            'emailAddress': 'megan.sullivan.demo@justinsurance.com',
            'username': 'msullivan.demo',
            'phone': '(555) 855-3347',
            'lastLoginDate': _days_ago(9),
            'departmentId': DEMO_DEPT_ID,
            'progress': 33.8,
            'timeSpent': 660,  # 11h
            'examPrepTime': 70,
            'courseName': 'North Carolina Health Pre-Licensing Course',
            'enrollmentStatus': 1,
            'primaryEnrollment': {'name': 'North Carolina Health Pre-Licensing Course', 'status': 1, 'progress': 33.8, 'timeSpent': 660},
            'enrollments': [
                {'name': 'North Carolina Health Pre-Licensing Course', 'status': 1, 'progress': 33.8, 'timeSpent': 660, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(30)},
                {'name': 'North Carolina Health Exam Prep Study Guide', 'status': 1, 'progress': 12.0, 'timeSpent': 70, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(12)},
                {'name': 'North Carolina Health Practice Exam v1', 'status': 2, 'progress': 100, 'timeSpent': 52, 'score': 58, 'dateCompleted': _days_ago(10), 'dateStarted': _days_ago(10)},
                {'name': 'North Carolina State Law - Health', 'status': 1, 'progress': 20, 'timeSpent': 18, 'score': None, 'dateCompleted': None, 'dateStarted': _days_ago(11)},
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
