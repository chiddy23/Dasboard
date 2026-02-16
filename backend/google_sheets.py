"""Google Sheets integration for exam scheduling data."""

import csv
import io
import requests
from datetime import datetime


SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1Hc7IUA8bZceLFlLdOPuGckDuV0MtqRcb5DPLeMhncbo/export?format=csv"

# Cache for sheet data
_sheet_cache = {'data': None, 'timestamp': None}
SHEET_CACHE_TTL = 300  # 5 minutes


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
    """Fetch and parse the Google Sheet exam data."""
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

    reader = csv.DictReader(io.StringIO(response.text))
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

    # Deduplicate by email (keep last occurrence, which is the most recent row)
    seen = {}
    for s in students:
        seen[s['email']] = s
    students = list(seen.values())

    print(f"[SHEET] Parsed {len(students)} unique exam students")

    _sheet_cache['data'] = students
    _sheet_cache['timestamp'] = now

    return students


def invalidate_sheet_cache():
    """Clear the sheet cache."""
    _sheet_cache['data'] = None
    _sheet_cache['timestamp'] = None
    print("[SHEET] Cache invalidated")


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


def update_sheet_passfail(email, result):
    """Write pass/fail result back to the Google Sheet's Pass/Fail column.

    Finds the row by email, then updates the Pass/Fail cell.
    Non-fatal: logs errors but doesn't raise.
    """
    try:
        gc = _get_gspread_client()
        if not gc:
            print("[SHEET WRITE] No Google Sheets credentials configured, skipping write-back")
            return False

        from config import Config
        sheet = gc.open_by_key(Config.GOOGLE_SHEET_ID).sheet1

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

        # Find the row with this email
        email_cells = sheet.col_values(email_col)
        row_num = None
        for i, cell_val in enumerate(email_cells, 1):
            if cell_val.strip().lower() == email.lower().strip():
                row_num = i
                break

        if not row_num:
            print(f"[SHEET WRITE] Email {email} not found in sheet")
            return False

        # Update the pass/fail cell
        sheet.update_cell(row_num, pf_col, result)
        print(f"[SHEET WRITE] Updated row {row_num}: {email} -> {result}")

        # Invalidate cache so next read picks up the change
        invalidate_sheet_cache()
        return True

    except Exception as e:
        print(f"[SHEET WRITE] Failed to write pass/fail for {email}: {e}")
        return False


def update_sheet_exam_date(email, exam_date, exam_time=''):
    """Write exam date/time back to the Google Sheet.

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
        sheet = gc.open_by_key(Config.GOOGLE_SHEET_ID).sheet1

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
