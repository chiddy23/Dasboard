"""SQLite snapshot storage for historical study data tracking.

Each sync cycle saves a point-in-time snapshot of every student's study metrics.
This builds a historical record for tracking study patterns over time.
"""

import sqlite3
import os
from datetime import datetime, timedelta

from config import Config
from utils.readiness import (
    calculate_readiness,
    _is_practice_exam, _is_state_law, _is_life_video, _is_health_video,
    _is_prelicensing, _get_enrollment_minutes, _get_enrollment_score,
    _get_enrollment_progress, _get_enrollment_status, _get_enrollment_name
)
from utils.gap_metrics import calculate_gap_metrics


def _get_connection():
    """Get a SQLite connection, creating the data directory if needed."""
    db_path = Config.SNAPSHOT_DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the snapshots table and indexes if they don't exist."""
    conn = _get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS study_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        total_time_min REAL DEFAULT 0,
        prelicense_progress REAL DEFAULT 0,
        exam_prep_progress REAL DEFAULT 0,
        practice_scores TEXT DEFAULT '',
        consecutive_passing INTEGER DEFAULT 0,
        readiness TEXT DEFAULT '',
        criteria_met TEXT DEFAULT '',
        study_gap_count INTEGER DEFAULT 0,
        total_gap_days INTEGER DEFAULT 0,
        largest_gap_days INTEGER DEFAULT 0,
        life_video_time REAL DEFAULT 0,
        health_video_time REAL DEFAULT 0,
        state_law_time REAL DEFAULT 0,
        state_law_completions INTEGER DEFAULT 0
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_snap_email ON study_snapshots(email)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_snap_time ON study_snapshots(snapshot_time)')

    # Exam overrides table (persists pass/fail and date changes across restarts)
    conn.execute('''CREATE TABLE IF NOT EXISTS exam_overrides (
        email TEXT PRIMARY KEY,
        pass_fail TEXT DEFAULT '',
        exam_date TEXT DEFAULT '',
        exam_time TEXT DEFAULT '',
        updated_at TEXT NOT NULL
    )''')

    # Allowed users table (active user allowlist for production lockdown)
    conn.execute('''CREATE TABLE IF NOT EXISTS allowed_users (
        email TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        added_by TEXT DEFAULT '',
        added_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )''')

    conn.commit()
    conn.close()


# ── Allowed Users (allowlist) functions ──────────────────────────────

def is_user_allowed(email):
    """Check if a user is on the allowlist.
    Returns True if allowlist is empty (not enforcing) or user is active."""
    email = email.lower().strip()
    conn = _get_connection()
    count = conn.execute(
        'SELECT COUNT(*) FROM allowed_users WHERE active = 1'
    ).fetchone()[0]
    if count == 0:
        conn.close()
        return True
    row = conn.execute(
        'SELECT 1 FROM allowed_users WHERE email = ? AND active = 1',
        (email,)
    ).fetchone()
    conn.close()
    return row is not None


def add_allowed_user(email, name='', added_by=''):
    """Add a user to the allowlist (or reactivate if previously removed)."""
    email = email.lower().strip()
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    existing = conn.execute(
        'SELECT name FROM allowed_users WHERE email = ?', (email,)
    ).fetchone()
    if existing:
        conn.execute(
            'UPDATE allowed_users SET active = 1, name = ?, added_by = ?, added_at = ? WHERE email = ?',
            (name or (existing['name'] if existing else ''), added_by, now, email)
        )
    else:
        conn.execute(
            'INSERT INTO allowed_users (email, name, added_by, added_at, active) VALUES (?, ?, ?, ?, 1)',
            (email, name, added_by, now)
        )
    conn.commit()
    conn.close()
    return True


def remove_allowed_user(email):
    """Soft-delete a user from the allowlist (set active=0)."""
    email = email.lower().strip()
    conn = _get_connection()
    conn.execute('UPDATE allowed_users SET active = 0 WHERE email = ?', (email,))
    conn.commit()
    conn.close()


def get_all_allowed_users():
    """Get all active allowed users as a list of dicts."""
    conn = _get_connection()
    rows = conn.execute(
        'SELECT email, name, added_by, added_at FROM allowed_users WHERE active = 1 ORDER BY added_at DESC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_allowlist_count():
    """Count of active allowed users. 0 means not enforcing."""
    conn = _get_connection()
    count = conn.execute(
        'SELECT COUNT(*) FROM allowed_users WHERE active = 1'
    ).fetchone()[0]
    conn.close()
    return count


def compute_snapshot_metrics(enrollments):
    """Compute study metrics from raw Absorb enrollments for a snapshot row.

    Returns a flat dict of metric values.
    """
    prelicensing_time = 0
    exam_prep_time = 0
    prelicensing_progress_values = []
    exam_prep_progress_values = []
    life_video_time = 0
    health_video_time = 0
    practice_scores = []
    state_law_time = 0
    state_law_completions = 0

    for e in enrollments:
        name = _get_enrollment_name(e)
        minutes = _get_enrollment_minutes(e)
        status = _get_enrollment_status(e)
        progress = _get_enrollment_progress(e)

        if _is_prelicensing(name):
            prelicensing_time += minutes
            prelicensing_progress_values.append(progress)

        if name and ('prep' in name.lower() or 'study' in name.lower()) and not _is_practice_exam(name):
            exam_prep_time += minutes
            exam_prep_progress_values.append(progress)

        if _is_practice_exam(name):
            practice_scores.append(_get_enrollment_score(e))

        if _is_state_law(name):
            state_law_time += minutes
            if status in (2, 3):
                state_law_completions += 1

        if _is_life_video(name):
            life_video_time += minutes
        if _is_health_video(name):
            health_video_time += minutes

    # Consecutive passing >= 80%
    consecutive = 0
    for score in practice_scores:
        if score >= 80:
            consecutive += 1
        else:
            break

    # Progress averages
    pre_progress = (
        round(sum(prelicensing_progress_values) / len(prelicensing_progress_values), 1)
        if prelicensing_progress_values else 0
    )
    prep_progress = (
        round(sum(exam_prep_progress_values) / len(exam_prep_progress_values), 1)
        if exam_prep_progress_values else 0
    )

    # Readiness and gap metrics
    readiness = calculate_readiness(enrollments)
    gap = calculate_gap_metrics(enrollments)

    return {
        'total_time_min': round(prelicensing_time + exam_prep_time, 1),
        'prelicense_progress': pre_progress,
        'exam_prep_progress': prep_progress,
        'practice_scores': ', '.join(str(round(s, 1)) for s in practice_scores),
        'consecutive_passing': consecutive,
        'readiness': readiness['status'],
        'criteria_met': f"{readiness['criteriaMet']}/{readiness['criteriaTotal']}",
        'study_gap_count': gap['study_gap_count'],
        'total_gap_days': gap['total_gap_days'],
        'largest_gap_days': gap['largest_gap_days'],
        'life_video_time': round(life_video_time, 1),
        'health_video_time': round(health_video_time, 1),
        'state_law_time': round(state_law_time, 1),
        'state_law_completions': state_law_completions,
    }


def save_snapshots_batch(snapshots):
    """Save a batch of snapshot dicts. Each must have 'email' + metric keys."""
    if not snapshots:
        return
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    conn.executemany(
        '''INSERT INTO study_snapshots
           (email, snapshot_time, total_time_min, prelicense_progress, exam_prep_progress,
            practice_scores, consecutive_passing, readiness, criteria_met,
            study_gap_count, total_gap_days, largest_gap_days,
            life_video_time, health_video_time, state_law_time, state_law_completions)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        [(
            s['email'], now, s.get('total_time_min', 0),
            s.get('prelicense_progress', 0), s.get('exam_prep_progress', 0),
            s.get('practice_scores', ''), s.get('consecutive_passing', 0),
            s.get('readiness', ''), s.get('criteria_met', ''),
            s.get('study_gap_count', 0), s.get('total_gap_days', 0),
            s.get('largest_gap_days', 0), s.get('life_video_time', 0),
            s.get('health_video_time', 0), s.get('state_law_time', 0),
            s.get('state_law_completions', 0)
        ) for s in snapshots]
    )
    conn.commit()
    conn.close()


def get_snapshots(email, limit=50):
    """Get snapshot history for a student, newest first."""
    conn = _get_connection()
    rows = conn.execute(
        'SELECT * FROM study_snapshots WHERE email = ? ORDER BY snapshot_time DESC LIMIT ?',
        (email.lower().strip(), limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cleanup_old_snapshots(days=90):
    """Delete snapshots older than N days to keep DB small."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = _get_connection()
    result = conn.execute(
        'DELETE FROM study_snapshots WHERE snapshot_time < ?', (cutoff,)
    )
    deleted = result.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"[SNAPSHOTS] Cleaned up {deleted} snapshots older than {days} days")


def set_override(email, pass_fail=None, exam_date=None, exam_time=None):
    """Set or update an exam override for a student."""
    email = email.lower().strip()
    conn = _get_connection()
    existing = conn.execute('SELECT * FROM exam_overrides WHERE email = ?', (email,)).fetchone()
    now = datetime.utcnow().isoformat()

    if existing:
        updates = []
        params = []
        if pass_fail is not None:
            updates.append('pass_fail = ?')
            params.append(pass_fail)
        if exam_date is not None:
            updates.append('exam_date = ?')
            params.append(exam_date)
        if exam_time is not None:
            updates.append('exam_time = ?')
            params.append(exam_time)
        updates.append('updated_at = ?')
        params.append(now)
        params.append(email)
        conn.execute(f'UPDATE exam_overrides SET {", ".join(updates)} WHERE email = ?', params)
    else:
        conn.execute(
            'INSERT INTO exam_overrides (email, pass_fail, exam_date, exam_time, updated_at) VALUES (?, ?, ?, ?, ?)',
            (email, pass_fail or '', exam_date or '', exam_time or '', now)
        )
    conn.commit()
    conn.close()


def get_all_overrides():
    """Get all exam overrides as dicts keyed by email."""
    conn = _get_connection()
    rows = conn.execute('SELECT * FROM exam_overrides').fetchall()
    conn.close()
    overrides = {}
    for r in rows:
        row = dict(r)
        overrides[row['email']] = row
    return overrides


# ---------------------------------------------------------------------------
# Google Sheet persistence (survives Render deploys)
# ---------------------------------------------------------------------------

SHEET_HEADERS = [
    'email', 'snapshot_time', 'total_time_min', 'prelicense_progress',
    'exam_prep_progress', 'practice_scores', 'consecutive_passing',
    'readiness', 'criteria_met', 'study_gap_count', 'total_gap_days',
    'largest_gap_days', 'life_video_time', 'health_video_time',
    'state_law_time', 'state_law_completions'
]


def _get_snapshot_sheet():
    """Get the snapshot Google Sheet worksheet. Returns None if not configured."""
    import json
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = Config.GOOGLE_SHEETS_CREDENTIALS_JSON
    sheet_id = Config.SNAPSHOT_SHEET_ID
    if not creds_json or not sheet_id:
        return None

    creds_data = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
    gc = gspread.authorize(credentials)
    return gc.open_by_key(sheet_id).sheet1


def save_snapshots_to_sheet(snapshots):
    """Append snapshot rows to the Google Sheet for durable storage.

    Each snapshot dict must have 'email' plus the metric keys.
    Non-fatal: logs errors but doesn't raise.
    """
    if not snapshots:
        return
    try:
        ws = _get_snapshot_sheet()
        if not ws:
            print("[SNAPSHOTS] No Google Sheet credentials or SNAPSHOT_SHEET_ID configured, skipping sheet save")
            return

        # Ensure headers exist (first row)
        existing = ws.row_values(1)
        if not existing or existing[0] != SHEET_HEADERS[0]:
            ws.update('A1', [SHEET_HEADERS])
            print("[SNAPSHOTS] Wrote headers to snapshot sheet")

        now = datetime.utcnow().isoformat()
        rows = []
        for s in snapshots:
            rows.append([
                s.get('email', ''),
                now,
                s.get('total_time_min', 0),
                s.get('prelicense_progress', 0),
                s.get('exam_prep_progress', 0),
                s.get('practice_scores', ''),
                s.get('consecutive_passing', 0),
                s.get('readiness', ''),
                s.get('criteria_met', ''),
                s.get('study_gap_count', 0),
                s.get('total_gap_days', 0),
                s.get('largest_gap_days', 0),
                s.get('life_video_time', 0),
                s.get('health_video_time', 0),
                s.get('state_law_time', 0),
                s.get('state_law_completions', 0),
            ])

        ws.append_rows(rows, value_input_option='RAW')
        print(f"[SNAPSHOTS] Appended {len(rows)} rows to Google Sheet")
    except Exception as e:
        print(f"[SNAPSHOTS] Failed to save to Google Sheet (non-fatal): {e}")


def load_snapshots_from_sheet():
    """Load historical snapshots from Google Sheet into SQLite.

    Called on startup so data survives Render deploys.
    Only imports rows that aren't already in SQLite (based on email + snapshot_time).
    """
    try:
        ws = _get_snapshot_sheet()
        if not ws:
            print("[SNAPSHOTS] No Google Sheet configured, skipping snapshot load")
            return 0

        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            print("[SNAPSHOTS] Snapshot sheet is empty (header only)")
            return 0

        headers = all_values[0]
        data_rows = all_values[1:]
        print(f"[SNAPSHOTS] Found {len(data_rows)} rows in Google Sheet")

        # Get existing snapshot times from SQLite to avoid duplicates
        conn = _get_connection()
        existing = set()
        for row in conn.execute('SELECT email, snapshot_time FROM study_snapshots').fetchall():
            existing.add((row['email'], row['snapshot_time']))

        # Parse sheet rows and insert missing ones
        new_count = 0
        now_iso = datetime.utcnow().isoformat()
        batch = []

        for row in data_rows:
            if len(row) < 2:
                continue
            # Map by header position
            row_dict = {}
            for i, h in enumerate(headers):
                row_dict[h] = row[i] if i < len(row) else ''

            email = (row_dict.get('email') or '').lower().strip()
            snap_time = row_dict.get('snapshot_time') or now_iso
            if not email:
                continue

            # Skip if already in SQLite
            if (email, snap_time) in existing:
                continue

            def safe_float(val, default=0):
                try:
                    return float(val) if val else default
                except (ValueError, TypeError):
                    return default

            def safe_int(val, default=0):
                try:
                    return int(float(val)) if val else default
                except (ValueError, TypeError):
                    return default

            batch.append((
                email, snap_time,
                safe_float(row_dict.get('total_time_min')),
                safe_float(row_dict.get('prelicense_progress')),
                safe_float(row_dict.get('exam_prep_progress')),
                row_dict.get('practice_scores', ''),
                safe_int(row_dict.get('consecutive_passing')),
                row_dict.get('readiness', ''),
                row_dict.get('criteria_met', ''),
                safe_int(row_dict.get('study_gap_count')),
                safe_int(row_dict.get('total_gap_days')),
                safe_int(row_dict.get('largest_gap_days')),
                safe_float(row_dict.get('life_video_time')),
                safe_float(row_dict.get('health_video_time')),
                safe_float(row_dict.get('state_law_time')),
                safe_int(row_dict.get('state_law_completions')),
            ))
            new_count += 1

        if batch:
            conn.executemany(
                '''INSERT INTO study_snapshots
                   (email, snapshot_time, total_time_min, prelicense_progress, exam_prep_progress,
                    practice_scores, consecutive_passing, readiness, criteria_met,
                    study_gap_count, total_gap_days, largest_gap_days,
                    life_video_time, health_video_time, state_law_time, state_law_completions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                batch
            )
            conn.commit()

        conn.close()
        print(f"[SNAPSHOTS] Loaded {new_count} new snapshots from Google Sheet into SQLite")
        return new_count
    except Exception as e:
        print(f"[SNAPSHOTS] Failed to load from Google Sheet (non-fatal): {e}")
        return 0


# ── Allowlist Google Sheets sync ──────────────────────────────────────

ALLOWLIST_HEADERS = ['email', 'name', 'added_by', 'added_at', 'active']


def _get_allowlist_sheet():
    """Get the AllowedUsers worksheet (second tab of snapshot sheet)."""
    import json
    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = Config.GOOGLE_SHEETS_CREDENTIALS_JSON
    sheet_id = Config.SNAPSHOT_SHEET_ID
    if not creds_json or not sheet_id:
        return None

    creds_data = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_key(sheet_id)

    try:
        return spreadsheet.worksheet('AllowedUsers')
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title='AllowedUsers', rows=100, cols=5)
        ws.update('A1', [ALLOWLIST_HEADERS])
        return ws


def save_allowlist_to_sheet():
    """Write the full allowlist to Google Sheets (overwrite). Non-fatal."""
    try:
        ws = _get_allowlist_sheet()
        if not ws:
            print("[ALLOWLIST] No Google Sheet configured, skipping sheet save")
            return
        users = get_all_allowed_users()
        ws.clear()
        ws.update('A1', [ALLOWLIST_HEADERS])
        if users:
            rows = [[u['email'], u['name'], u['added_by'], u['added_at'], '1'] for u in users]
            ws.append_rows(rows, value_input_option='RAW')
        print(f"[ALLOWLIST] Saved {len(users)} allowed users to Google Sheet")
    except Exception as e:
        print(f"[ALLOWLIST] Failed to save to Google Sheet (non-fatal): {e}")


def load_allowlist_from_sheet():
    """Load allowlist from Google Sheet into SQLite on startup."""
    try:
        ws = _get_allowlist_sheet()
        if not ws:
            print("[ALLOWLIST] No Google Sheet configured, skipping allowlist load")
            return 0
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            print("[ALLOWLIST] Allowlist sheet is empty")
            return 0
        headers = all_values[0]
        data_rows = all_values[1:]
        conn = _get_connection()
        loaded = 0
        for row in data_rows:
            row_dict = {h: row[i] if i < len(row) else '' for i, h in enumerate(headers)}
            email = (row_dict.get('email') or '').lower().strip()
            if not email:
                continue
            if row_dict.get('active', '1') != '1':
                continue
            existing = conn.execute('SELECT 1 FROM allowed_users WHERE email = ?', (email,)).fetchone()
            if not existing:
                conn.execute(
                    'INSERT INTO allowed_users (email, name, added_by, added_at, active) VALUES (?, ?, ?, ?, 1)',
                    (email, row_dict.get('name', ''), row_dict.get('added_by', ''),
                     row_dict.get('added_at', datetime.utcnow().isoformat()))
                )
                loaded += 1
        conn.commit()
        conn.close()
        print(f"[ALLOWLIST] Loaded {loaded} new allowed users from Google Sheet")
        return loaded
    except Exception as e:
        print(f"[ALLOWLIST] Failed to load from Google Sheet (non-fatal): {e}")
        return 0


# Initialize DB on import
init_db()

# Load historical snapshots from Google Sheet (survives Render deploys)
load_snapshots_from_sheet()

# Load allowlist from Google Sheet (survives Render deploys)
load_allowlist_from_sheet()
