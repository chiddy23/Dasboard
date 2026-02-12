"""Google Sheets write-back integration using gspread.

Handles writing Absorb LMS study data back to the exam Google Sheet.
Kept separate from google_sheets.py (read-only CSV) so the read path
works even without service account credentials.
"""

import json
import os
import gspread
from google.oauth2.service_account import Credentials
from config import Config

# Column header names for sync columns (added to the right of existing data)
SYNC_COLUMNS = [
    'LMS Total Time (min)',
    'Life Video Time (min)',
    'Health Video Time (min)',
    'Pre-License Progress (%)',
    'Exam Prep Progress (%)',
    'Practice Exam Scores',
    'Consecutive Passing',
    'State Laws Time (min)',
    'State Laws Completions',
    'Last Login',
    'Department',
    'Phone',
    'Study Gaps',
    'Total Gap Days',
    'Largest Gap (days)',
    'Last Gap Date',
    'Readiness',
    'Criteria Met',
    'Last Sync',
]

_gspread_client = None


def _get_gspread_client():
    """Lazily initialize and return a gspread client with service account auth."""
    global _gspread_client
    if _gspread_client is not None:
        return _gspread_client

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]

    creds_json = Config.GOOGLE_SHEETS_CREDENTIALS_JSON
    creds_file = Config.GOOGLE_SHEETS_CREDENTIALS_FILE

    if creds_json:
        creds_info = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
    elif creds_file and os.path.exists(creds_file):
        credentials = Credentials.from_service_account_file(creds_file, scopes=scopes)
    else:
        raise RuntimeError(
            'Google Sheets credentials not configured. '
            'Set GOOGLE_SHEETS_CREDENTIALS_JSON or GOOGLE_SHEETS_CREDENTIALS_FILE env var.'
        )

    _gspread_client = gspread.authorize(credentials)
    return _gspread_client


def get_worksheet():
    """Get the first worksheet of the configured Google Sheet."""
    client = _get_gspread_client()
    spreadsheet = client.open_by_key(Config.GOOGLE_SHEET_ID)
    return spreadsheet.sheet1


def ensure_sync_columns(worksheet):
    """
    Ensure the sync columns exist as headers on the right side of the sheet.
    Idempotent: if columns already exist, finds them; if not, appends them.
    Returns the column index (1-based) of the first sync column.
    """
    headers = worksheet.row_values(1)

    # Check if first sync column already exists
    if SYNC_COLUMNS[0] in headers:
        return headers.index(SYNC_COLUMNS[0]) + 1  # 1-based

    # Add headers at the end
    start_col = len(headers) + 1
    header_cells = []
    for i, col_name in enumerate(SYNC_COLUMNS):
        header_cells.append(gspread.Cell(1, start_col + i, col_name))

    worksheet.update_cells(header_cells)
    print(f"[SHEET WRITER] Created {len(SYNC_COLUMNS)} sync columns starting at column {start_col}")
    return start_col


def find_email_column(worksheet):
    """Find the column index (1-based) that contains Email addresses."""
    headers = worksheet.row_values(1)
    for i, h in enumerate(headers):
        if h.strip().lower() == 'email':
            return i + 1  # 1-based
    return 2  # Default: column B


def build_email_to_row_map(worksheet, email_col):
    """
    Build a mapping of email -> row number.
    Returns dict {lowercase_email: row_number (1-based)}.
    """
    email_values = worksheet.col_values(email_col)
    email_map = {}
    for row_idx, email in enumerate(email_values):
        if row_idx == 0:  # Skip header
            continue
        email_clean = (email or '').strip().lower()
        if email_clean:
            email_map[email_clean] = row_idx + 1  # 1-based row
    return email_map


def write_student_rows_batch(worksheet, rows_data, sync_col_start):
    """
    Write sync data for multiple students in a single batch API call.
    rows_data: list of (row_number, student_data_dict) tuples.
    """
    cells = []
    for row_number, student_data in rows_data:
        for i, col_name in enumerate(SYNC_COLUMNS):
            value = student_data.get(col_name, '')
            cells.append(gspread.Cell(row_number, sync_col_start + i, str(value)))

    if cells:
        worksheet.update_cells(cells, value_input_option='USER_ENTERED')
        print(f"[SHEET WRITER] Wrote {len(rows_data)} rows ({len(cells)} cells) to sheet")
