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

    conn.commit()
    conn.close()


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


# Initialize DB on import
init_db()
