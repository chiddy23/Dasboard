"""Google Sheets integration for exam scheduling data."""

import csv
import io
import re
import requests
from datetime import datetime


SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1Hc7IUA8bZceLFlLdOPuGckDuV0MtqRcb5DPLeMhncbo/export?format=csv"

# Cache for admin sheet data (global)
_sheet_cache = {'data': None, 'timestamp': None}
SHEET_CACHE_TTL = 300  # 5 minutes

# Cache for per-user sheet data
_user_sheet_cache = {}  # {user_email: {'data': [...], 'timestamp': datetime}}
USER_SHEET_CACHE_TTL = 300  # 5 minutes


def parse_sheet_id(url_or_id):
    """Extract Google Sheet ID from a URL or raw ID string.

    Handles:
      - https://docs.google.com/spreadsheets/d/SHEET_ID/edit#gid=0
      - https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv
      - https://docs.google.com/spreadsheets/d/SHEET_ID
      - Raw ID string (alphanumeric + hyphens + underscores, 20+ chars)
    """
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    # Try extracting from URL
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    # Check if it's a raw sheet ID
    if re.match(r'^[a-zA-Z0-9_-]{20,}$', url_or_id):
        return url_or_id
    return None


def format_exam_date(date_str):
    """Parse and format exam date for display."""
    if not date_str:
        return 'TBD'
    date_str = date_str.strip()
    # Try M/D/YYYY (CSV export format)
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%B %d, %Y', '%b %d, %Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%b %d, %Y')
        except ValueError:
            continue
    return date_str


def parse_exam_date_for_sort(date_str):
    """Parse exam date string to datetime for sorting."""
    if not date_str:
        return datetime.min
    date_str = date_str.strip()
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%B %d, %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


def fetch_exam_sheet():
    """Fetch and parse the admin Google Sheet exam data."""
    now = datetime.utcnow()

    # Check cache
    if _sheet_cache['data'] is not None and _sheet_cache['timestamp']:
        age = (now - _sheet_cache['timestamp']).total_seconds()
        if age < SHEET_CACHE_TTL:
            print(f"[SHEET] Using cached data (age: {int(age)}s)")
            return _sheet_cache['data']

    print("[SHEET] Fetching fresh data from Google Sheets...")

    try:
        response = requests.get(SHEET_CSV_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[SHEET] Failed to fetch: {e}")
        if _sheet_cache['data'] is not None:
            return _sheet_cache['data']
        return []

    students = _parse_sheet_csv(response.text)
    print(f"[SHEET] Parsed {len(students)} unique exam students")

    _sheet_cache['data'] = students
    _sheet_cache['timestamp'] = now

    return students


def invalidate_sheet_cache():
    """Clear the sheet cache."""
    _sheet_cache['data'] = None
    _sheet_cache['timestamp'] = None
    print("[SHEET] Cache invalidated")


def _parse_sheet_csv(text):
    """Parse CSV text into the standard exam student format. Shared by admin + user sheet."""
    reader = csv.DictReader(io.StringIO(text))
    students = []

    for row in reader:
        email = (row.get('Email') or '').strip().lower()
        if not email:
            continue

        raw_date = (row.get('Exam Date') or '').strip()

        # Weekly tracking data (T-5 through T-0)
        weekly = []
        for week in ['T-5', 'T-4', 'T-3', 'T-2', 'T-1']:
            status = (row.get(f'{week} Status') or '').strip()
            hours = (row.get(f'{week} Hours') or '').strip()
            practice = (row.get(f'{week} Practice %') or '').strip()
            notes = (row.get(f'{week} Notes') or '').strip()
            if status or hours or practice or notes:
                weekly.append({
                    'week': week,
                    'status': status,
                    'hours': hours,
                    'practice': practice,
                    'notes': notes
                })

        students.append({
            'name': (row.get('Student Name') or '').strip(),
            'email': email,
            'phone': (row.get('Phone') or '').strip(),
            'examDate': raw_date,
            'examDateFormatted': format_exam_date(raw_date),
            'examTime': (row.get('Exam Time') or '').strip(),
            'state': (row.get('State') or '').strip(),
            'course': (row.get('Course') or '').strip(),
            'agencyOwner': (row.get('Agency Owner') or '').strip(),
            'passFail': (row.get('Pass/Fail') or '').strip(),
            'finalOutcome': (row.get('Final Outcome') or '').strip(),
            # Extended tracking data
            'alertDate': (row.get('Alert Date') or '').strip(),
            'studyHoursAtExam': (row.get('Study Hours at Exam') or '').strip(),
            'finalPractice': (row.get('Final Practice %') or '').strip(),
            'chaptersComplete': (row.get('Chapters Complete') or '').strip(),
            'videosWatched': (row.get('Videos Watched') or '').strip(),
            'stateLawsDone': (row.get('State Laws Done') or '').strip(),
            'studyConsistency': (row.get('Study Consistency') or '').strip(),
            't0Sent': (row.get('T-0 Sent') or '').strip(),
            'weeklyTracking': weekly,
        })

    # Deduplicate by email: keep last occurrence, but preserve pass/fail from any row
    seen = {}
    passfail_by_email = {}
    for s in students:
        e = s['email']
        if s['passFail']:
            passfail_by_email[e] = s['passFail']
        seen[e] = s
    for e, s in seen.items():
        if not s['passFail'] and e in passfail_by_email:
            s['passFail'] = passfail_by_email[e]
    return list(seen.values())


def fetch_user_exam_sheet(sheet_id, user_email):
    """Fetch and parse a user's Google Sheet exam data (per-user cache)."""
    user_email = user_email.lower().strip()
    now = datetime.utcnow()

    # Check per-user cache
    if user_email in _user_sheet_cache:
        cache = _user_sheet_cache[user_email]
        age = (now - cache['timestamp']).total_seconds()
        if age < USER_SHEET_CACHE_TTL:
            print(f"[USER SHEET] Using cached data for {user_email} (age: {int(age)}s)")
            return cache['data']

    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    print(f"[USER SHEET] Fetching fresh data for {user_email}...")

    try:
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[USER SHEET] Failed to fetch for {user_email}: {e}")
        if user_email in _user_sheet_cache:
            return _user_sheet_cache[user_email]['data']
        return []

    students = _parse_sheet_csv(response.text)
    print(f"[USER SHEET] Parsed {len(students)} unique exam students for {user_email}")

    _user_sheet_cache[user_email] = {'data': students, 'timestamp': now}
    return students


def validate_user_sheet(sheet_id):
    """Validate a Google Sheet by testing fetch and checking required columns."""
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        response = requests.get(csv_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return {'valid': False, 'error': f'Could not access sheet. Make sure it is shared as "Anyone with the link can view". Error: {e}'}

    reader = csv.DictReader(io.StringIO(response.text))
    headers = reader.fieldnames or []
    header_lower = [h.lower().strip() for h in headers]

    if 'email' not in header_lower:
        return {'valid': False, 'error': 'Sheet is missing required "Email" column'}
    if 'exam date' not in header_lower:
        return {'valid': False, 'error': 'Sheet is missing required "Exam Date" column'}

    rows = list(reader)
    return {
        'valid': True,
        'row_count': len(rows),
        'columns': headers,
    }


def invalidate_user_sheet_cache(user_email):
    """Clear cached data for a specific user's sheet."""
    user_email = user_email.lower().strip()
    if user_email in _user_sheet_cache:
        del _user_sheet_cache[user_email]
        print(f"[USER SHEET] Cache invalidated for {user_email}")


def _get_gspread_client():
    """Get authenticated gspread client using service account credentials."""
    import json
    import gspread
    from google.oauth2.service_account import Credentials

    from config import Config
    creds_json = Config.GOOGLE_SHEETS_CREDENTIALS_JSON
    if not creds_json:
        return None

    creds_data = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
    return gspread.authorize(credentials)


def update_sheet_passfail(email, result, sheet_id=None):
    """Write pass/fail result back to a Google Sheet's Pass/Fail column.

    If sheet_id is provided, writes to that sheet; otherwise uses admin sheet.
    Finds the row by email, then updates the Pass/Fail cell.
    Non-fatal: logs errors but doesn't raise.
    """
    try:
        gc = _get_gspread_client()
        if not gc:
            print("[SHEET WRITE] No Google Sheets credentials configured, skipping write-back")
            return False

        from config import Config
        target_id = sheet_id or Config.GOOGLE_SHEET_ID
        sheet = gc.open_by_key(target_id).sheet1

        # Find the email column and pass/fail column
        headers = sheet.row_values(1)
        email_col = None
        pf_col = None
        for i, h in enumerate(headers, 1):
            if h.strip().lower() == 'email':
                email_col = i
            if h.strip().lower() == 'pass/fail':
                pf_col = i

        if not email_col or not pf_col:
            print(f"[SHEET WRITE] Could not find Email (col {email_col}) or Pass/Fail (col {pf_col}) columns")
            return False

        # Find ALL rows with this email (students can have multiple exam entries)
        email_cells = sheet.col_values(email_col)
        row_nums = []
        for i, cell_val in enumerate(email_cells, 1):
            if cell_val.strip().lower() == email.lower().strip():
                row_nums.append(i)

        if not row_nums:
            print(f"[SHEET WRITE] Email {email} not found in sheet")
            return False

        # Update the pass/fail cell in ALL matching rows
        for row_num in row_nums:
            sheet.update_cell(row_num, pf_col, result)
        print(f"[SHEET WRITE] Updated {len(row_nums)} row(s) for {email} -> {result}")

        # Invalidate cache so next read picks up the change
        invalidate_sheet_cache()
        return True

    except Exception as e:
        print(f"[SHEET WRITE] Failed to write pass/fail for {email}: {e}")
        return False


def update_sheet_exam_date(email, exam_date, exam_time='', sheet_id=None):
    """Write exam date/time back to a Google Sheet.

    If sheet_id is provided, writes to that sheet; otherwise uses admin sheet.
    Finds the row by email, then updates the Exam Date and Exam Time cells.
    exam_date should be in YYYY-MM-DD format; it gets converted to M/D/YYYY for the sheet.
    Non-fatal: logs errors but doesn't raise.
    """
    try:
        gc = _get_gspread_client()
        if not gc:
            print("[SHEET WRITE] No Google Sheets credentials configured, skipping date write-back")
            return False

        from config import Config
        target_id = sheet_id or Config.GOOGLE_SHEET_ID
        sheet = gc.open_by_key(target_id).sheet1

        headers = sheet.row_values(1)
        email_col = None
        date_col = None
        time_col = None
        for i, h in enumerate(headers, 1):
            hl = h.strip().lower()
            if hl == 'email':
                email_col = i
            if hl == 'exam date':
                date_col = i
            if hl == 'exam time':
                time_col = i

        if not email_col or not date_col:
            print(f"[SHEET WRITE] Could not find Email (col {email_col}) or Exam Date (col {date_col}) columns")
            return False

        # Find the row with this email
        email_cells = sheet.col_values(email_col)
        row_num = None
        for i, cell_val in enumerate(email_cells, 1):
            if cell_val.strip().lower() == email.lower().strip():
                row_num = i
                break

        if not row_num:
            print(f"[SHEET WRITE] Email {email} not found in sheet for date update")
            return False

        # Convert YYYY-MM-DD to M/D/YYYY for the sheet
        sheet_date = exam_date
        try:
            dt = datetime.strptime(exam_date, '%Y-%m-%d')
            sheet_date = f"{dt.month}/{dt.day}/{dt.year}"
        except ValueError:
            pass

        sheet.update_cell(row_num, date_col, sheet_date)
        if time_col and exam_time:
            sheet.update_cell(row_num, time_col, exam_time)

        print(f"[SHEET WRITE] Updated row {row_num}: {email} -> date={sheet_date} time={exam_time}")

        invalidate_sheet_cache()
        return True

    except Exception as e:
        print(f"[SHEET WRITE] Failed to write exam date for {email}: {e}")
        return False


def update_sheet_contact(email, name='', new_email='', phone='', sheet_id=None):
    """Write contact info (name, email, phone) back to a Google Sheet.

    If sheet_id is provided, writes to that sheet; otherwise uses admin sheet.
    Finds the row by current email, then updates the specified fields.
    Non-fatal: logs errors but doesn't raise.
    """
    try:
        gc = _get_gspread_client()
        if not gc:
            print("[SHEET WRITE] No Google Sheets credentials configured, skipping contact write-back")
            return False

        from config import Config
        target_id = sheet_id or Config.GOOGLE_SHEET_ID
        sheet = gc.open_by_key(target_id).sheet1

        headers = sheet.row_values(1)
        email_col = None
        name_col = None
        phone_col = None
        for i, h in enumerate(headers, 1):
            hl = h.strip().lower()
            if hl == 'email':
                email_col = i
            if hl == 'student name':
                name_col = i
            if hl == 'phone':
                phone_col = i

        if not email_col:
            print("[SHEET WRITE] Could not find Email column")
            return False

        # Find the row with this email
        email_cells = sheet.col_values(email_col)
        row_num = None
        for i, cell_val in enumerate(email_cells, 1):
            if cell_val.strip().lower() == email.lower().strip():
                row_num = i
                break

        if not row_num:
            print(f"[SHEET WRITE] Email {email} not found in sheet for contact update")
            return False

        # Update fields that were provided
        if name and name_col:
            sheet.update_cell(row_num, name_col, name)
        if new_email:
            sheet.update_cell(row_num, email_col, new_email)
        if phone and phone_col:
            sheet.update_cell(row_num, phone_col, phone)

        updated = []
        if name:
            updated.append(f"name={name}")
        if new_email:
            updated.append(f"email={new_email}")
        if phone:
            updated.append(f"phone={phone}")
        print(f"[SHEET WRITE] Updated row {row_num} contact: {', '.join(updated)}")

        invalidate_sheet_cache()
        return True

    except Exception as e:
        print(f"[SHEET WRITE] Failed to write contact for {email}: {e}")
        return False
