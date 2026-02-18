"""Background scheduler for automatic Absorb data sync.

Runs on a configurable timer, authenticates with Absorb independently,
reads student emails from the Google Sheet, fetches their enrollment data,
and caches the results so the exam tab loads instantly.

Requires env vars:
    SYNC_ABSORB_USERNAME  - Absorb admin account username
    SYNC_ABSORB_PASSWORD  - Absorb admin account password
    SYNC_INTERVAL_HOURS   - How often to sync (default: 6)
"""

import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config


class SyncScheduler:
    """Periodic background sync of Absorb data for exam-scheduled students."""

    def __init__(self, interval_hours=6):
        self.interval = interval_hours * 3600  # seconds
        self._timer = None
        self._running = False
        self.last_sync = None
        self.last_result = None
        self.last_cached = 0

    def start(self):
        """Start the scheduler. First sync runs after a short delay."""
        if self._running:
            return
        self._running = True
        # Let the app finish starting before first sync
        self._schedule_next(delay=60)
        print(f"[SYNC SCHEDULER] Started - will sync every {self.interval // 3600}h")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._timer:
            self._timer.cancel()
        print("[SYNC SCHEDULER] Stopped")

    def _schedule_next(self, delay=None):
        """Schedule the next sync run."""
        if not self._running:
            return
        wait = delay if delay is not None else self.interval
        self._timer = threading.Timer(wait, self._run_sync)
        self._timer.daemon = True
        self._timer.start()

    def _run_sync(self):
        """Execute one sync cycle, then schedule the next."""
        print(f"[SYNC SCHEDULER] Starting scheduled sync at {datetime.utcnow().isoformat()}")

        try:
            cached = self._do_sync()
            self.last_sync = datetime.utcnow()
            self.last_result = 'success'
            self.last_cached = cached
            print(f"[SYNC SCHEDULER] Completed: {cached} students cached")
        except Exception as e:
            self.last_sync = datetime.utcnow()
            self.last_result = f'error: {str(e)}'
            self.last_cached = 0
            print(f"[SYNC SCHEDULER] Failed: {e}")
        finally:
            self._schedule_next()

    def _do_sync(self):
        """Read sheet emails, fetch Absorb data, cache results. Returns count cached."""
        from absorb_api import AbsorbAPIClient
        from google_sheets import fetch_exam_sheet
        from utils import format_student_for_response
        import routes.exam as exam_module

        username = Config.SYNC_ABSORB_USERNAME
        password = Config.SYNC_ABSORB_PASSWORD

        if not username or not password:
            print("[SYNC SCHEDULER] Missing SYNC_ABSORB_USERNAME / SYNC_ABSORB_PASSWORD")
            return 0

        # 1. Read student emails from Google Sheet (CSV export, no auth needed)
        sheet_students = fetch_exam_sheet()
        if not sheet_students:
            print("[SYNC SCHEDULER] No students found in sheet")
            return 0

        emails = [s['email'] for s in sheet_students if s.get('email')]
        print(f"[SYNC SCHEDULER] Found {len(emails)} emails in sheet")

        # 2. Authenticate with Absorb using stored admin credentials
        client = AbsorbAPIClient()
        auth = client.authenticate_user(username, password)
        if not auth.get('success'):
            raise Exception('Absorb authentication failed')
        client.set_token(auth['token'])

        # 3. Batch look up students in Absorb
        found_users = client.get_users_by_emails_batch(emails)
        print(f"[SYNC SCHEDULER] Found {len(found_users)}/{len(emails)} users in Absorb")

        # 4. Process each found user (fetch enrollments) in parallel
        cached_count = 0

        if found_users:
            max_workers = min(30, len(found_users))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_user = {
                    executor.submit(client._process_single_user, user): user
                    for user in found_users
                }

                completed = 0
                for future in as_completed(future_to_user):
                    completed += 1
                    user = future_to_user[future]
                    email = (user.get('emailAddress') or user.get('EmailAddress') or '').lower().strip()

                    try:
                        result = future.result()
                        if result:
                            formatted = format_student_for_response(result)
                            exam_module._exam_absorb_cache[email] = {
                                'raw': result,
                                'formatted': formatted
                            }
                            cached_count += 1
                        else:
                            exam_module._exam_absorb_cache[email] = None
                    except Exception as e:
                        print(f"[SYNC SCHEDULER] Error processing {email}: {e}")
                        exam_module._exam_absorb_cache[email] = None

                    if completed % 20 == 0 or completed == len(found_users):
                        print(f"[SYNC SCHEDULER] Processed {completed}/{len(found_users)} ({cached_count} cached)")

        # 5. Mark uncached emails as None (not found in Absorb)
        for email in emails:
            if email not in exam_module._exam_absorb_cache:
                exam_module._exam_absorb_cache[email] = None

        # Update cache timestamp
        exam_module._exam_absorb_timestamp = datetime.utcnow()

        # 6. Save study snapshots to SQLite + Google Sheet for historical tracking
        try:
            from snapshot_db import compute_snapshot_metrics, save_snapshots_batch, cleanup_old_snapshots, save_snapshots_to_sheet

            snapshots = []
            for email in emails:
                cached = exam_module._exam_absorb_cache.get(email)
                if cached and cached.get('raw'):
                    enrollments = cached['raw'].get('enrollments', [])
                    if enrollments:
                        metrics = compute_snapshot_metrics(enrollments)
                        metrics['email'] = email
                        snapshots.append(metrics)

            if snapshots:
                save_snapshots_batch(snapshots)
                print(f"[SYNC SCHEDULER] Saved {len(snapshots)} study snapshots to SQLite")
                # Also persist to Google Sheet (survives Render deploys)
                save_snapshots_to_sheet(snapshots)

            cleanup_old_snapshots(days=90)
        except Exception as e:
            print(f"[SYNC SCHEDULER] Snapshot save failed (non-fatal): {e}")

        return cached_count

    def get_status(self):
        """Return scheduler status for API consumption."""
        next_run = None
        if self._timer and self._timer.is_alive():
            next_run = f'{self.interval // 3600}h cycle'

        return {
            'enabled': True,
            'intervalHours': self.interval / 3600,
            'lastSync': self.last_sync.isoformat() if self.last_sync else None,
            'lastResult': self.last_result,
            'lastCached': self.last_cached,
            'nextRun': next_run,
        }


# Module-level instance
_scheduler = None


def start_sync_scheduler():
    """Start the background sync scheduler if credentials are configured."""
    global _scheduler

    username = Config.SYNC_ABSORB_USERNAME
    password = Config.SYNC_ABSORB_PASSWORD

    if not username or not password:
        print("[SYNC SCHEDULER] Not started - set SYNC_ABSORB_USERNAME and SYNC_ABSORB_PASSWORD to enable")
        return

    interval = Config.SYNC_INTERVAL_HOURS
    _scheduler = SyncScheduler(interval_hours=interval)
    _scheduler.start()


def get_scheduler_info():
    """Get scheduler status for API endpoint."""
    if _scheduler:
        return _scheduler.get_status()
    return {
        'enabled': False,
        'intervalHours': Config.SYNC_INTERVAL_HOURS,
        'lastSync': None,
        'lastResult': None,
        'lastCached': 0,
        'nextRun': None,
    }
