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
        })

    print(f"[SHEET] Parsed {len(students)} exam students")

    _sheet_cache['data'] = students
    _sheet_cache['timestamp'] = now

    return students


def invalidate_sheet_cache():
    """Clear the sheet cache."""
    _sheet_cache['data'] = None
    _sheet_cache['timestamp'] = None
    print("[SHEET] Cache invalidated")
