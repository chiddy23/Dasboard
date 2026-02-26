"""Demo mode: anonymized real student data for presentations.

Fetches real student data from the Google Sheet + Absorb API,
replaces personal info (names, emails, phone) with fake data,
and serves it under a demo department. All study data, enrollments,
scores, and progress remain real.
"""

import uuid
import time

DEMO_DEPT_ID = 'de000000-0000-0000-0000-de0000000001'
DEMO_DEPT_NAME = 'Demo Agency - Dashboard Preview'

FAKE_NAMES = [
    ('James', 'Anderson'), ('Maria', 'Thompson'), ('Robert', 'Garcia'),
    ('Jennifer', 'Martinez'), ('Michael', 'Robinson'), ('Sarah', 'Clark'),
    ('David', 'Rodriguez'), ('Emily', 'Lewis'), ('Daniel', 'Walker'),
    ('Ashley', 'Hall'), ('Christopher', 'Allen'), ('Jessica', 'Young'),
    ('Matthew', 'King'), ('Amanda', 'Wright'), ('Andrew', 'Lopez'),
    ('Stephanie', 'Hill'), ('Joshua', 'Scott'), ('Nicole', 'Green'),
    ('Brandon', 'Adams'), ('Rachel', 'Baker'), ('Ryan', 'Nelson'),
    ('Megan', 'Carter'), ('Kevin', 'Mitchell'), ('Lauren', 'Perez'),
    ('Justin', 'Roberts'), ('Amber', 'Turner'), ('Tyler', 'Phillips'),
    ('Kayla', 'Campbell'), ('Nathan', 'Parker'), ('Brittany', 'Evans'),
    ('Marcus', 'Flores'), ('Diana', 'Rivera'), ('Derek', 'Nguyen'),
    ('Lisa', 'Chen'), ('Jason', 'Patel'), ('Sophie', 'Torres'),
    ('Jordan', 'Hayes'), ('Sydney', 'Sullivan'), ('Oscar', 'Ortega'),
    ('Erika', 'Vasquez'), ('Connor', 'Reed'), ('Samantha', 'Brooks'),
    ('Adrian', 'Price'), ('Natalie', 'Barnes'), ('Ethan', 'Howard'),
    ('Vanessa', 'Coleman'), ('Ian', 'Russell'), ('Alexis', 'Diaz'),
    ('Luke', 'Foster'), ('Brianna', 'Sanders'),
]

# Persistent demo cache
_demo_cache = {
    'raw': None,
    'timestamp': 0,
    'id_map': {},           # demo_id -> real_id
    'reverse_id_map': {},   # real_id_lower -> demo_id
    'email_map': {},        # real_email -> index
    'name_map': {},         # demo_id -> (firstName, lastName, demo_email)
}
DEMO_CACHE_TTL = 300  # 5 minutes


def _generate_demo_id(index):
    """Generate consistent demo ID from index."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f'demo-student-{index}'))


def _fake_name(index):
    """Get fake name pair for an index."""
    return FAKE_NAMES[index % len(FAKE_NAMES)]


def _fake_email(first, last):
    """Generate fake email from name."""
    return f'{first.lower()}.{last.lower()}.demo@justinsurance.com'


def _fake_phone(index):
    """Generate fake phone number."""
    return f'(555) {100 + index:03d}-{1000 + index * 7:04d}'


# ── Public API ────────────────────────────────────────────────────────

def is_demo_dept(dept_id):
    """Check if a department ID is the demo department."""
    if not dept_id:
        return False
    return dept_id.lower().strip() == DEMO_DEPT_ID.lower()


def is_demo_student(student_id):
    """Check if this is a demo student ID."""
    if not student_id:
        return False
    return student_id in _demo_cache.get('id_map', {})


def get_real_id(demo_id):
    """Look up real Absorb student ID from demo ID."""
    return _demo_cache.get('id_map', {}).get(demo_id)


def get_demo_name(demo_id):
    """Get fake name info for a demo student.

    Returns (firstName, lastName, demoEmail).
    """
    return _demo_cache.get('name_map', {}).get(
        demo_id, ('Demo', 'Student', 'demo@justinsurance.com')
    )


def get_demo_email_lookup():
    """Get real_email -> demo info mapping for ALL registered students.

    Used by the exam tab to anonymize entries after matching.
    Returns dict: real_email -> {firstName, lastName, fullName, email, demoId}
    """
    lookup = {}
    for real_email, index in _demo_cache.get('email_map', {}).items():
        first, last = _fake_name(index)
        demo_email = _fake_email(first, last)
        demo_id = _generate_demo_id(index)
        lookup[real_email] = {
            'firstName': first,
            'lastName': last,
            'fullName': f'{first} {last}',
            'email': demo_email,
            'demoId': demo_id,
        }
    return lookup


def is_demo_cache_valid():
    """Check if demo cache is still valid."""
    if not _demo_cache['raw']:
        return False
    return (time.time() - _demo_cache['timestamp']) < DEMO_CACHE_TTL


def get_cached_demo_students():
    """Get demo students from cache if valid, else None."""
    if is_demo_cache_valid():
        return _demo_cache['raw']
    return None


def register_sheet_emails(sheet_students):
    """Assign consistent fake name indices to all sheet students.

    Call BEFORE build_demo_from_real so that ALL students (including
    those not found in Absorb) get a fake name assignment.
    """
    for i, s in enumerate(sheet_students):
        email = (s.get('email') or '').lower().strip()
        if email and email not in _demo_cache['email_map']:
            _demo_cache['email_map'][email] = i


def build_demo_from_real(real_students):
    """Take real processed students, anonymize personal info, cache and return.

    Args:
        real_students: List of student dicts from _process_single_user()

    Returns:
        List of anonymized student dicts (real study data, fake personal info)
    """
    demo_students = []
    id_map = {}
    reverse_id_map = {}
    name_map = {}

    for student in real_students:
        real_id = student.get('id') or student.get('Id') or ''
        real_email = (student.get('emailAddress') or '').lower().strip()

        # Look up index from email_map (registered from sheet)
        index = _demo_cache['email_map'].get(real_email)
        if index is None:
            # Not in sheet — assign next available index
            index = len(_demo_cache['email_map'])
            _demo_cache['email_map'][real_email] = index

        demo_id = _generate_demo_id(index)
        first, last = _fake_name(index)
        demo_email = _fake_email(first, last)

        # Shallow copy and anonymize personal fields only
        anonymized = dict(student)
        anonymized['id'] = demo_id
        anonymized['firstName'] = first
        anonymized['lastName'] = last
        anonymized['emailAddress'] = demo_email
        anonymized['username'] = f'{first[0].lower()}{last.lower()}.demo'
        anonymized['phone'] = _fake_phone(index)
        anonymized['departmentId'] = DEMO_DEPT_ID
        # Internal fields for matching (not sent to frontend)
        anonymized['_realEmail'] = real_email
        anonymized['_realId'] = real_id

        id_map[demo_id] = real_id
        reverse_id_map[real_id.lower()] = demo_id
        name_map[demo_id] = (first, last, demo_email)

        demo_students.append(anonymized)

    _demo_cache['raw'] = demo_students
    _demo_cache['timestamp'] = time.time()
    _demo_cache['id_map'] = id_map
    _demo_cache['reverse_id_map'] = reverse_id_map
    _demo_cache['name_map'] = name_map

    print(f"[DEMO] Built {len(demo_students)} anonymized students from real data")
    return demo_students
