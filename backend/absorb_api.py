"""Absorb LMS API Client for JustInsurance Student Dashboard."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import Config


class AbsorbAPIError(Exception):
    """Custom exception for Absorb API errors."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


# Global session with connection pooling for better performance
_session = None

def get_session():
    """Get or create a requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        # Configure connection pooling and retries
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=retry_strategy
        )
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def parse_time_to_minutes(time_value) -> int:
    """Parse time value to minutes. Handles .NET TimeSpan format: [d.]HH:MM:SS[.fffffff]

    Examples:
        "01:26:11.9878697"     -> 86 min (1h 26m)
        "1.13:02:39.9878697"   -> 2222 min (1d 13h 2m)
        "37:02:39"             -> 2222 min (37h 2m)
    """
    if not time_value:
        return 0
    if isinstance(time_value, (int, float)):
        return int(time_value)
    if isinstance(time_value, str):
        try:
            parts = time_value.split(':')
            if len(parts) >= 2:
                days = 0
                first = parts[0]
                # Check for days prefix: "1.13" in "1.13:02:39.9878697"
                if '.' in first:
                    day_hour = first.split('.')
                    days = int(day_hour[0])
                    hours = int(day_hour[1])
                else:
                    hours = int(first)
                mins = int(parts[1])
                return days * 1440 + hours * 60 + mins
            return int(float(time_value))
        except (ValueError, TypeError):
            return 0
    return 0


class AbsorbAPIClient:
    """Client for interacting with Absorb LMS REST API."""

    def __init__(self):
        self.base_url = Config.ABSORB_BASE_URL
        self.api_key = Config.ABSORB_API_KEY
        self.private_key = Config.ABSORB_PRIVATE_KEY
        self._token = None
        self._token_expiry = None
        self._session = get_session()

    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Get headers for API requests.

        Uses 'Bearer <token>' on the Authorization header to match the
        Absorb Apps Script reference and the lesson/attempt endpoints that
        required Bearer prefix. Absorb historically accepted raw tokens on
        some endpoints but that path is being deprecated and caused
        intermittent 401s under parallel load on /users/{id}/enrollments
        calls fanning out 50-at-a-time. Bearer is the standard and works
        across every endpoint we've tested.
        """
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if include_auth and self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        return headers

    # Kept for backwards-compat with call sites that explicitly asked for
    # Bearer (e.g. get_enrollment_lessons, get_lesson_attempts). Both now
    # return identical headers; method kept so we don't touch unrelated
    # call sites in this fix.
    def _get_headers_bearer(self) -> Dict[str, str]:
        return self._get_headers()

    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate a user against Absorb API."""
        url = f"{self.base_url}/Authenticate"
        payload = {
            "Username": username,
            "Password": password,
            "PrivateKey": self.private_key
        }
        headers = self._get_headers(include_auth=False)

        try:
            response = self._session.post(url, json=payload, headers=headers, timeout=30)
            print(f"[AUTH] Status: {response.status_code}")

            if response.status_code == 200:
                token = response.text.strip().strip('"')
                return {"success": True, "token": token}
            elif response.status_code in [400, 401]:
                raise AbsorbAPIError("Invalid username or password", 401)
            else:
                raise AbsorbAPIError(f"Authentication failed: {response.text}", response.status_code)
        except requests.exceptions.RequestException as e:
            raise AbsorbAPIError(f"Connection error: {str(e)}")

    def set_token(self, token: str):
        """Set the authentication token for subsequent requests."""
        self._token = token
        self._token_expiry = datetime.utcnow() + timedelta(hours=4)

    def get_user_by_email(self, email: str, name_hint: str = '') -> Optional[Dict[str, Any]]:
        """Look up a user by email address across all departments.
        Uses name_hint (from Google Sheet) to search Absorb by name, then matches by email."""
        url = f"{self.base_url}/users"
        email_lower = email.lower().strip()

        def _match_email(users_list):
            """Find exact email match in a list of users (case-insensitive)."""
            for u in users_list:
                u_email = (u.get('emailAddress') or u.get('EmailAddress') or '').lower().strip()
                if u_email == email_lower:
                    return u
            return None

        # Strategy 1: Search by last name (most reliable - Absorb _search matches name fields)
        if name_hint:
            parts = name_hint.strip().split()
            last_name = parts[-1] if parts else ''
            if last_name and len(last_name) >= 2:
                try:
                    params = {"_search": last_name, "_limit": 100}
                    response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        users = data if isinstance(data, list) else []
                        print(f"[API] Name search '{last_name}' returned {len(users)} users for {email_lower}")
                        match = _match_email(users)
                        if match:
                            print(f"[API] Found match by name for {email_lower}")
                            return match
                    else:
                        print(f"[API] Name search failed with status {response.status_code} for {email_lower}")
                except Exception as e:
                    print(f"[API] Name search error for {name_hint}: {e}")

        # Strategy 2: Search by full email
        try:
            params = {"_search": email_lower, "_limit": 50}
            response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
            if response.status_code == 200:
                data = response.json()
                users = data if isinstance(data, list) else []
                print(f"[API] Email search returned {len(users)} users for {email_lower}")
                match = _match_email(users)
                if match:
                    print(f"[API] Found match by email for {email_lower}")
                    return match
            else:
                print(f"[API] Email search failed with status {response.status_code} for {email_lower}")
        except Exception as e:
            print(f"[API] Email search error for {email}: {e}")

        # Strategy 3: OData filter (original approach)
        try:
            params = {"_filter": f"emailAddress eq '{email}'", "_limit": 1}
            response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
            if response.status_code == 200:
                data = response.json()
                users = data if isinstance(data, list) else []
                if users:
                    return users[0]
        except Exception as e:
            pass

        return None

    def lookup_and_process_student(self, email: str, name_hint: str = '') -> Optional[Dict[str, Any]]:
        """Look up a student by email and process their enrollment data."""
        try:
            user = self.get_user_by_email(email, name_hint)
            if not user:
                return None
            return self._process_single_user(user)
        except Exception as e:
            print(f"[API] Error processing exam student {email}: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user by their ID (works cross-department for admin users).

        Args:
            user_id: The user's GUID

        Returns:
            User object if found, None otherwise

        Raises:
            AbsorbAPIError: If the API request fails
        """
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = self._session.get(url, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise AbsorbAPIError(f"User not found: {user_id}", status_code=404)
            else:
                raise AbsorbAPIError(
                    f"Failed to fetch user {user_id}: {response.status_code}",
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )
        except requests.RequestException as e:
            raise AbsorbAPIError(f"Network error fetching user {user_id}: {str(e)}")

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a user's profile fields in Absorb LMS.

        Args:
            user_id: The user's GUID
            updates: Dictionary of fields to update (PascalCase keys: FirstName, LastName, EmailAddress, Phone)

        Returns:
            Updated user object from Absorb API

        Raises:
            AbsorbAPIError: If the API request fails
        """
        url = f"{self.base_url}/users/{user_id}"
        try:
            response = self._session.put(url, json=updates, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise AbsorbAPIError(f"User not found: {user_id}", status_code=404)
            elif response.status_code == 400:
                error_msg = response.text or "Invalid update data"
                raise AbsorbAPIError(f"Bad request: {error_msg}", status_code=400)
            else:
                raise AbsorbAPIError(
                    f"Failed to update user {user_id}: {response.status_code}",
                    status_code=response.status_code,
                    response=response.json() if response.content else None
                )
        except requests.RequestException as e:
            raise AbsorbAPIError(f"Network error updating user {user_id}: {str(e)}")

    def fetch_user_by_email_odata(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user by email using OData filter (simple, direct approach)."""
        # Skip if we already know token is expired (avoid spamming 400 failed requests)
        if getattr(self, '_token_expired', False):
            return None

        url = f"{self.base_url}/users"
        try:
            params = {"_filter": f"emailAddress eq '{email}'", "_limit": 1}
            response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)

            # Log first attempt to debug (then suppress)
            if not hasattr(self, '_logged_odata_attempt'):
                print(f"[API DEBUG] OData search attempt for: {email}")
                print(f"[API DEBUG] Status: {response.status_code}")
                print(f"[API DEBUG] Has token: {bool(self._token)}")
                self._logged_odata_attempt = True

            if response.status_code == 401:
                self._token_expired = True
                print(f"[API] Absorb token expired during cross-dept lookup — skipping remaining emails")
                return None

            if response.status_code == 200:
                data = response.json()

                # Parse response - could be list or dict with 'users' key
                if isinstance(data, list):
                    users = data
                elif isinstance(data, dict):
                    users = data.get('users', data.get('Users', []))
                else:
                    users = []

                # Log what we got back (first attempt only)
                if not hasattr(self, '_logged_odata_response'):
                    print(f"[API DEBUG] Response type: {type(data)}")
                    print(f"[API DEBUG] Dict keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                    print(f"[API DEBUG] Users found: {len(users)}")
                    if not users:
                        print(f"[API DEBUG] Empty result - OData email search may not work cross-dept")
                    self._logged_odata_response = True

                if users:
                    return users[0]
            else:
                # Log non-200 responses (first email only to avoid spam)
                if not hasattr(self, '_logged_odata_error'):
                    print(f"[API] OData fetch failed for {email}: Status {response.status_code}")
                    print(f"[API] Response: {response.text[:200]}")
                    self._logged_odata_error = True
        except Exception as e:
            print(f"[API] Error fetching {email}: {e}")
        return None

    def get_users_by_emails_batch(self, target_emails: List[str]) -> List[Dict[str, Any]]:
        """Get specific users by email addresses (parallel individual lookups).

        Args:
            target_emails: List of email addresses to find

        Returns:
            List of user objects matching the provided emails
        """
        found_users = []

        print(f"[API] Fetching {len(target_emails)} users individually (parallel OData filter)...")

        # Use ThreadPoolExecutor for parallel lookups
        max_workers = min(50, len(target_emails))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_email = {
                executor.submit(self.fetch_user_by_email_odata, email): email
                for email in target_emails
            }

            for future in as_completed(future_to_email):
                try:
                    user = future.result()
                    if user:
                        found_users.append(user)
                except AbsorbAPIError as e:
                    if e.status_code == 401:
                        # Token expired - cancel remaining futures and propagate
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise
                except Exception:
                    pass  # Skip individual lookup failures

        print(f"[API] COMPLETE: Found {len(found_users)}/{len(target_emails)} users")
        return found_users

    def get_users_by_department(self, department_id: str) -> List[Dict[str, Any]]:
        """Get ALL users in a department, working around Absorb API limitations.

        Absorb /users has two hard constraints that break naive pagination:
          1. _limit cannot exceed 1000 (422 ErrorGeneric)
          2. _offset past the first page on a filtered query silently returns
             0 users (any _offset > 0 combined with _filter returns nothing,
             regardless of _sort/_orderby variant)

        Strategy:
          Phase 1: fetch with _limit=1000. If totalItems <= 1000 we're done
                   (handles ~all depts in a single API call).
          Phase 2: if totalItems > 1000, split by lastLoginDate year buckets
                   plus a 'never logged in' bucket (eq null). Each bucket is
                   a separate _filter query that starts fresh at offset 0,
                   bypassing the broken pagination. Fetched in parallel.
          Phase 3: if any single year bucket still hits the 1000 cap,
                   recursively subdivide that year into quarters, then
                   months if needed. Hard stops at month granularity.
          Phase 4: deduplicate by user id and return.

        Returns a list of raw Absorb user dicts — same shape as before.
        """
        print(f"[API] get_users_by_department: {department_id}")

        # ─── Phase 1: single-call fast path ───────────────────────────────
        first_users, total_items = self._fetch_users_page(
            filter_expr=f"departmentId eq guid'{department_id}'",
            limit=1000,
        )

        if total_items is None:
            # Older Absorb tenants may not return totalItems; fall back to
            # trusting the single-page result.
            print(f"[API] COMPLETE: single-call path, {len(first_users)} users "
                  f"(no totalItems reported)")
            return first_users

        if len(first_users) >= total_items:
            print(f"[API] COMPLETE: single-call path, {len(first_users)}/{total_items} users")
            return first_users

        print(f"[API] Single-call returned {len(first_users)} of {total_items} total — "
              f"splitting by lastLoginDate year buckets in parallel")

        # ─── Phase 2: year-range buckets (parallel) ───────────────────────
        all_by_id: Dict[str, Dict[str, Any]] = {}
        for u in first_users:
            uid = u.get('id') or u.get('Id')
            if uid:
                all_by_id[uid] = u

        # Build the bucket list. Use yearly buckets from 2015 through current
        # year + 1 (safety margin for future-dated records). Year ranges are
        # expressed as half-open intervals [jan1 ... jan1 of next year), and
        # we include a 'null' bucket for users who have never logged in.
        current_year = datetime.utcnow().year
        year_range_args = []
        for year in range(2015, current_year + 2):
            start = f"{year}-01-01T00:00:00"
            end = f"{year + 1}-01-01T00:00:00"
            year_range_args.append((year, start, end))

        def fetch_year_bucket(year_tuple):
            year, start, end = year_tuple
            f = (f"departmentId eq guid'{department_id}' "
                 f"and lastLoginDate gt datetime'{start}' "
                 f"and lastLoginDate lt datetime'{end}'")
            try:
                users, sub_total = self._fetch_users_page(f, limit=1000)
                return ('year', year, f, users, sub_total)
            except Exception as e:
                print(f"[API] Year bucket {year} failed: {e}")
                return ('year', year, f, [], None)

        def fetch_null_bucket():
            f = f"departmentId eq guid'{department_id}' and lastLoginDate eq null"
            try:
                users, sub_total = self._fetch_users_page(f, limit=1000)
                return ('null', None, f, users, sub_total)
            except Exception as e:
                print(f"[API] Null bucket failed: {e}")
                return ('null', None, f, [], None)

        bucket_results = []
        with ThreadPoolExecutor(max_workers=min(12, len(year_range_args) + 1)) as ex:
            futs = [ex.submit(fetch_year_bucket, yt) for yt in year_range_args]
            futs.append(ex.submit(fetch_null_bucket))
            for fut in as_completed(futs):
                try:
                    bucket_results.append(fut.result())
                except Exception as e:
                    print(f"[API] Year bucket worker exception: {e}")

        # Merge the bucket users + identify any that hit the 1000 cap and
        # need to be subdivided further.
        overflow_buckets = []  # list of (bucket_kind, year, filter_expr, sub_total)
        for kind, year, fexpr, users, sub_total in bucket_results:
            for u in users:
                uid = u.get('id') or u.get('Id')
                if uid and uid not in all_by_id:
                    all_by_id[uid] = u
            if sub_total is not None and sub_total > 1000 and len(users) >= 1000:
                print(f"[API] Bucket {kind}={year} has {sub_total} users, needs split")
                overflow_buckets.append((kind, year, fexpr, sub_total))
            else:
                print(f"[API] Bucket {kind}={year}: {len(users)} users (total reported: {sub_total})")

        # ─── Phase 3: recursive split for over-1000 year buckets ──────────
        if overflow_buckets:
            for kind, year, _, _ in overflow_buckets:
                if kind != 'year' or year is None:
                    continue
                print(f"[API] Splitting year {year} into quarters...")
                quarter_users = self._split_bucket_quarterly(department_id, year)
                for u in quarter_users:
                    uid = u.get('id') or u.get('Id')
                    if uid and uid not in all_by_id:
                        all_by_id[uid] = u

        all_users = list(all_by_id.values())
        print(f"[API] COMPLETE: multi-bucket path, {len(all_users)} unique users "
              f"(reported total: {total_items})")
        if len(all_users) < total_items:
            print(f"[API] WARNING: missing {total_items - len(all_users)} users — "
                  f"may indicate a bucket exceeded the cap without being detected")
        return all_users

    def _fetch_users_page(self, filter_expr: str, limit: int = 1000):
        """Execute a single /users query. Returns (users_list, total_items).

        total_items may be None if the response shape doesn't include it.
        Raises AbsorbAPIError on 401; returns ([], None) on other errors so
        callers (bucket workers) don't explode the whole fetch.
        """
        url = f"{self.base_url}/users"
        params = {"_filter": filter_expr, "_limit": limit, "_offset": 0}
        response = self._session.get(
            url, params=params, headers=self._get_headers(), timeout=120
        )
        if response.status_code == 401:
            print(f"[API] Token expired - need to re-authenticate")
            raise AbsorbAPIError("Session expired. Please log in again.", 401)
        if response.status_code != 200:
            print(f"[API] /users filter fetch failed: {response.status_code} - {response.text[:200]}")
            return [], None
        data = response.json()
        if isinstance(data, dict):
            users = data.get('users') or data.get('Users') or []
            total = data.get('totalItems') or data.get('TotalItems')
            return users, total
        if isinstance(data, list):
            return data, None
        return [], None

    def _split_bucket_quarterly(self, department_id: str, year: int) -> List[Dict[str, Any]]:
        """Fetch users from a single year in 4 parallel quarter-range calls.

        If any quarter still exceeds 1000, recursively split into months.
        """
        quarters = [
            (1, f"{year}-01-01T00:00:00", f"{year}-04-01T00:00:00"),
            (2, f"{year}-04-01T00:00:00", f"{year}-07-01T00:00:00"),
            (3, f"{year}-07-01T00:00:00", f"{year}-10-01T00:00:00"),
            (4, f"{year}-10-01T00:00:00", f"{year + 1}-01-01T00:00:00"),
        ]

        def fetch_quarter(q):
            qnum, qstart, qend = q
            f = (f"departmentId eq guid'{department_id}' "
                 f"and lastLoginDate gt datetime'{qstart}' "
                 f"and lastLoginDate lt datetime'{qend}'")
            try:
                users, sub_total = self._fetch_users_page(f, limit=1000)
                return qnum, qstart, qend, users, sub_total
            except Exception as e:
                print(f"[API] Quarter {year}Q{qnum} failed: {e}")
                return qnum, qstart, qend, [], None

        merged: Dict[str, Dict[str, Any]] = {}
        overflow_quarters = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for fut in as_completed([ex.submit(fetch_quarter, q) for q in quarters]):
                qnum, qstart, qend, users, sub_total = fut.result()
                for u in users:
                    uid = u.get('id') or u.get('Id')
                    if uid and uid not in merged:
                        merged[uid] = u
                if sub_total is not None and sub_total > 1000 and len(users) >= 1000:
                    print(f"[API] Quarter {year}Q{qnum} has {sub_total} users, splitting into months")
                    overflow_quarters.append((qnum, qstart, qend))
                else:
                    print(f"[API] Quarter {year}Q{qnum}: {len(users)} users")

        # Month-level fallback for quarters that still overflowed. A dept
        # with > 1000 users logging in within a single quarter is extreme
        # but we handle it with monthly buckets. No further recursion past
        # months — if one month still has > 1000, we warn and return what
        # we have (very unlikely for any real agency dept).
        for qnum, qstart, qend in overflow_quarters:
            # Build month ranges inside this quarter
            # qstart/qend strings like '2026-01-01T00:00:00'
            start_year = int(qstart[:4])
            start_month = int(qstart[5:7])
            month_ranges = []
            for m_offset in range(3):
                m = start_month + m_offset
                y = start_year
                next_m = m + 1
                next_y = y
                if next_m > 12:
                    next_m = 1
                    next_y = y + 1
                m_start = f"{y:04d}-{m:02d}-01T00:00:00"
                m_end = f"{next_y:04d}-{next_m:02d}-01T00:00:00"
                month_ranges.append((y, m, m_start, m_end))

            def fetch_month(mt):
                my, mm, ms, me = mt
                f = (f"departmentId eq guid'{department_id}' "
                     f"and lastLoginDate gt datetime'{ms}' "
                     f"and lastLoginDate lt datetime'{me}'")
                try:
                    users, sub_total = self._fetch_users_page(f, limit=1000)
                    return my, mm, users, sub_total
                except Exception as e:
                    print(f"[API] Month {my}-{mm:02d} failed: {e}")
                    return my, mm, [], None

            with ThreadPoolExecutor(max_workers=3) as ex:
                for fut in as_completed([ex.submit(fetch_month, mt) for mt in month_ranges]):
                    my, mm, users, sub_total = fut.result()
                    for u in users:
                        uid = u.get('id') or u.get('Id')
                        if uid and uid not in merged:
                            merged[uid] = u
                    if sub_total is not None and sub_total > 1000 and len(users) >= 1000:
                        print(f"[API] WARNING: month {my}-{mm:02d} has {sub_total} users, "
                              f"exceeds cap and month-level is our smallest split. "
                              f"Missing {sub_total - len(users)} users from this bucket.")
                    else:
                        print(f"[API] Month {my}-{mm:02d}: {len(users)} users")

        return list(merged.values())

    def get_department(self, department_id: str) -> Dict[str, Any]:
        """Get department information. Tries capitalized then lowercase path.

        Falls back silently to a placeholder on any failure so callers that
        don't handle exceptions keep working, but logs the real failure so
        the issue isn't invisible.
        """
        for variant in ('Departments', 'departments'):
            url = f"{self.base_url}/{variant}/{department_id}"
            try:
                response = self._session.get(url, headers=self._get_headers(), timeout=30)
                if response.status_code == 200:
                    return response.json()
                print(f"[API] get_department {variant}/{department_id} returned {response.status_code}: {response.text[:200]}")
            except Exception as e:
                print(f"[API] get_department {variant}/{department_id} exception: {e}")
        return {'id': department_id, 'name': 'Department', 'Name': 'Department'}

    def get_user_enrollments(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all course enrollments for a user."""
        # Use exact endpoint pattern from working Apps Script with _limit parameter
        url = f"{self.base_url}/users/{user_id}/enrollments"
        params = {"_limit": 100}

        try:
            response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
            if response.status_code == 401:
                raise AbsorbAPIError("Session expired. Please log in again.", 401)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('enrollments') or data.get('Enrollments') or []
        except AbsorbAPIError:
            raise  # Propagate auth errors
        except Exception as e:
            # Try alternate casing as fallback
            try:
                url = f"{self.base_url}/Users/{user_id}/Enrollments"
                response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
                if response.status_code == 401:
                    raise AbsorbAPIError("Session expired. Please log in again.", 401)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get('enrollments') or data.get('Enrollments') or []
            except AbsorbAPIError:
                raise
            except:
                pass

        return []

    def get_enrollment_lessons(self, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        """List lessons inside a user's enrollment on a specific course."""
        url = f"{self.base_url}/users/{user_id}/enrollments/{course_id}/lessons"
        params = {"_limit": 200}
        try:
            response = self._session.get(
                url,
                params=params,
                headers=self._get_headers_bearer(),
                timeout=30,
            )
            auth_mode = 'bearer'
            if response.status_code == 401:
                response = self._session.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=30,
                )
                auth_mode = 'raw'
            print(f"[API] get_enrollment_lessons {course_id} auth={auth_mode} status={response.status_code}")
            if response.status_code != 200:
                print(f"[API] lessons body: {response.text[:300]}")
                return []
            data = response.json()
            if isinstance(data, list):
                lessons = data
            elif isinstance(data, dict):
                lessons = data.get('lessons') or data.get('Lessons') or []
                if not lessons:
                    print(f"[API] lessons dict keys: {list(data.keys())[:10]}  sample: {str(data)[:300]}")
            else:
                lessons = []
            print(f"[API] lessons returned {len(lessons)} entries")
            if lessons:
                print(f"[API] first lesson keys: {list(lessons[0].keys())[:20] if isinstance(lessons[0], dict) else 'not a dict'}")
                # Dump full first lesson once per call so we can see field types/values
                print(f"[API] first lesson full: {str(lessons[0])[:800]}")
            return lessons
        except Exception as e:
            print(f"[API] get_enrollment_lessons {course_id} exception: {e}")
            return []

    def get_lesson_attempts(self, user_id: str, course_id: str, lesson_id: str) -> List[Dict[str, Any]]:
        """List all attempts a user has made on a specific lesson."""
        url = f"{self.base_url}/users/{user_id}/enrollments/{course_id}/lessons/{lesson_id}/attempts"
        params = {"_limit": 100}
        try:
            response = self._session.get(
                url,
                params=params,
                headers=self._get_headers_bearer(),
                timeout=30,
            )
            auth_mode = 'bearer'
            if response.status_code == 401:
                response = self._session.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=30,
                )
                auth_mode = 'raw'
            print(f"[API] get_lesson_attempts lesson={lesson_id} auth={auth_mode} status={response.status_code}")
            if response.status_code != 200:
                if response.status_code not in (404,):
                    print(f"[API] attempts body: {response.text[:300]}")
                return []
            data = response.json()
            if isinstance(data, list):
                attempts = data
            elif isinstance(data, dict):
                attempts = data.get('attempts') or data.get('Attempts') or []
                if not attempts:
                    print(f"[API] attempts dict keys: {list(data.keys())[:10]}  sample: {str(data)[:300]}")
            else:
                attempts = []
            print(f"[API] attempts returned {len(attempts)} for lesson {lesson_id}")
            if attempts:
                print(f"[API] first attempt keys: {list(attempts[0].keys())[:20] if isinstance(attempts[0], dict) else 'not a dict'}")
                print(f"[API] first attempt sample: {str(attempts[0])[:400]}")
            return attempts
        except Exception as e:
            print(f"[API] get_lesson_attempts lesson={lesson_id} exception: {e}")
            return []

    def get_practice_exam_attempts(self, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        """Fetch all attempts across all lessons in a practice-exam enrollment.

        Returns a flat list of normalized attempt dicts:
            {
                'score': float,           # 0-100
                'date': str,              # ISO-ish date string (raw from Absorb)
                'status': str,            # e.g. 'Complete', 'Failed', or raw status
                'duration_minutes': int,  # if available
                'lesson_id': str,         # source lesson
            }
        Attempts are sorted newest-first. Lessons with no attempts are skipped.
        """
        lessons = self.get_enrollment_lessons(user_id, course_id)
        if not lessons:
            return []

        all_attempts: List[Dict[str, Any]] = []

        def _fetch_for_lesson(lesson):
            # If the lesson object itself carries an inline attempts array,
            # prefer that — saves the round trip entirely.
            inline = lesson.get('attempts') or lesson.get('Attempts')
            if isinstance(inline, list) and inline and isinstance(inline[0], dict):
                print(f"[API] lesson has INLINE attempts array ({len(inline)} items) — using without separate fetch")
                raw = inline
            else:
                # Per Absorb docs the URL wants the course-level LessonId,
                # which lives under the 'lessonId' key on the lesson enrollment
                # object. The bare 'id' field is the per-user lesson-enrollment
                # record ID and returns 404 on the /attempts endpoint.
                lesson_id = (
                    lesson.get('lessonId') or lesson.get('LessonId') or
                    lesson.get('id') or lesson.get('Id')
                )
                if not lesson_id:
                    return []
                raw = self.get_lesson_attempts(user_id, course_id, lesson_id)
            normalized = []
            for a in raw or []:
                # Score field — multiple possible names across tenants
                score = (
                    a.get('score') if a.get('score') is not None else
                    a.get('Score') if a.get('Score') is not None else
                    a.get('result') if a.get('result') is not None else
                    a.get('Result')
                )
                try:
                    score_val = float(score) if score is not None else None
                except (ValueError, TypeError):
                    score_val = None
                if score_val is None:
                    # Skip attempts without a score — nothing to count
                    continue
                # Attempt records use startDate / completionDate (not the
                # dateAttempted/dateCompleted pattern used on enrollments).
                # Prefer completionDate (when available) since that's when
                # the scored attempt was finalized; fall back through legacy
                # field names for safety across tenants.
                date = (
                    a.get('completionDate') or a.get('CompletionDate') or
                    a.get('startDate') or a.get('StartDate') or
                    a.get('dateCompleted') or a.get('DateCompleted') or
                    a.get('dateAttempted') or a.get('DateAttempted') or
                    a.get('dateStarted') or a.get('DateStarted') or
                    a.get('dateCreated') or a.get('DateCreated') or
                    ''
                )
                status = a.get('status') or a.get('Status') or ''
                # Duration: Absorb attempt records use timeSpentTicks in
                # .NET ticks (1 tick = 100 nanoseconds, so 10M ticks/sec).
                # ticks / 10_000_000 = seconds, / 60 = minutes.
                duration_min = 0
                ticks = a.get('timeSpentTicks') or a.get('TimeSpentTicks')
                if ticks is not None:
                    try:
                        duration_min = int(float(ticks) / 10_000_000 / 60)
                    except (ValueError, TypeError):
                        duration_min = 0
                if duration_min == 0:
                    duration = (
                        a.get('duration') or a.get('Duration') or
                        a.get('timeSpent') or a.get('TimeSpent') or 0
                    )
                    try:
                        duration_min = parse_time_to_minutes(duration) if isinstance(duration, str) else int(duration or 0)
                    except Exception:
                        duration_min = 0
                normalized.append({
                    'score': round(score_val, 2),
                    'date': date,
                    'status': str(status),
                    'duration_minutes': duration_min,
                    'lesson_id': lesson_id,
                })
            return normalized

        max_workers = min(10, max(1, len(lessons)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_for_lesson, l): l for l in lessons}
            for fut in as_completed(futures):
                try:
                    all_attempts.extend(fut.result() or [])
                except Exception as e:
                    print(f"[API] get_practice_exam_attempts worker exception: {e}")

        # Sort newest first by raw date string (ISO sorts lexicographically)
        all_attempts.sort(key=lambda a: a.get('date') or '', reverse=True)
        return all_attempts

    def _is_prelicensing_course(self, course_name: str) -> bool:
        """Check if a course is a Pre-Licensing/Pre-License course."""
        if not course_name:
            return False
        name_lower = course_name.lower()
        # Match "pre-license", "pre-licensing", "prelicense", "prelicensing", etc.
        if ('pre-licens' in name_lower or
                'prelicens' in name_lower or
                'pre licens' in name_lower):
            return True
        # Also match courses containing "license"/"licensing" (broader catch)
        # but exclude exam prep courses that happen to contain "license"
        if 'licens' in name_lower:
            if not ('prep' in name_lower or 'practice' in name_lower or 'study' in name_lower):
                return True
        return False

    def _is_exam_prep_course(self, course_name: str) -> bool:
        """Check if a course is an Exam Prep course (includes practice exams)."""
        if not course_name:
            return False
        name_lower = course_name.lower()
        return 'prep' in name_lower or 'study' in name_lower or 'practice' in name_lower

    def _is_module_or_chapter(self, course_name: str) -> bool:
        """Check if a course name indicates it's a module/chapter."""
        if not course_name:
            return False
        name_lower = course_name.lower()
        return ('module' in name_lower or
                'chapter' in name_lower or
                'lesson' in name_lower or
                'unit' in name_lower)

    def _find_primary_course(self, enrollments: List[Dict]) -> tuple:
        """
        Find the primary course for dashboard display.
        Prioritizes: Main Pre-Licensing course > Chapters/Modules > Other in-progress
        Returns: (primary_enrollment, calculated_progress, total_time_spent, display_name)
        """
        if not enrollments:
            return None, 0, 0, 'No Course'

        # Categorize enrollments
        prelicensing_main = None
        prelicensing_chapters = []
        exam_prep_courses = []
        other_in_progress = None

        for e in enrollments:
            course_name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
            status = e.get('status') or e.get('Status') or 0

            if self._is_prelicensing_course(course_name):
                if not self._is_module_or_chapter(course_name):
                    # This is the main Pre-Licensing course (e.g., "Alabama Life & Health Pre-license Course")
                    prelicensing_main = e
                else:
                    # This is a chapter/module of the pre-licensing course
                    prelicensing_chapters.append(e)
            elif self._is_module_or_chapter(course_name):
                # Chapters without "pre-license" in name - likely still part of curriculum
                prelicensing_chapters.append(e)
            elif self._is_exam_prep_course(course_name):
                exam_prep_courses.append(e)
            elif status != 2 and other_in_progress is None:
                # First non-completed other course
                other_in_progress = e

        # Combine all pre-licensing related courses (main + chapters)
        all_prelicensing = ([prelicensing_main] if prelicensing_main else []) + prelicensing_chapters

        if all_prelicensing:
            # Use main pre-licensing course's progress directly (Absorb tracks true overall %)
            # Only fall back to averaging chapters if no main course exists
            primary = prelicensing_main or all_prelicensing[0]

            if prelicensing_main:
                prog = prelicensing_main.get('progress') or prelicensing_main.get('Progress') or 0
                try:
                    avg_progress = float(prog) if prog else 0
                except (ValueError, TypeError):
                    avg_progress = 0
            else:
                # No main course found, average chapter progress as fallback
                valid_progress = []
                for e in all_prelicensing:
                    prog = e.get('progress') or e.get('Progress') or 0
                    try:
                        prog = float(prog) if prog else 0
                        valid_progress.append(prog)
                    except (ValueError, TypeError):
                        pass
                avg_progress = sum(valid_progress) / len(valid_progress) if valid_progress else 0
            # Try each time field, use first non-zero (avoids truthy "00:00:00" short-circuiting)
            main_time = 0
            for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                _tv = primary.get(_tf)
                if _tv:
                    parsed = parse_time_to_minutes(_tv)
                    if parsed > 0:
                        main_time = parsed
                        break

            # If main course reports 0 time, sum chapter times as fallback
            # (same logic as calculate_prelicensing_totals in student detail modal)
            if main_time == 0 and len(all_prelicensing) > 1:
                for e in all_prelicensing:
                    for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                        _tv = e.get(_tf)
                        if _tv:
                            parsed = parse_time_to_minutes(_tv)
                            if parsed > 0:
                                main_time += parsed
                                break

            # Determine display name
            if prelicensing_main:
                display_name = prelicensing_main.get('name') or prelicensing_main.get('Name') or prelicensing_main.get('courseName') or prelicensing_main.get('CourseName') or 'Pre-License Course'
            else:
                display_name = 'Pre-License Course'

            return primary, avg_progress, main_time, display_name

        # Fall back to exam prep, other in-progress, or first enrollment
        if exam_prep_courses:
            primary = exam_prep_courses[0]
        elif other_in_progress:
            primary = other_in_progress
        else:
            primary = enrollments[0]

        # Handle progress (might be string or number)
        progress = primary.get('progress') or primary.get('Progress') or 0
        try:
            progress = float(progress) if progress else 0
        except (ValueError, TypeError):
            progress = 0

        # Handle time spent - try each field, use first non-zero
        time_spent = 0
        for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
            _tv = primary.get(_tf)
            if _tv:
                parsed = parse_time_to_minutes(_tv)
                if parsed > 0:
                    time_spent = parsed
                    break

        display_name = primary.get('name') or primary.get('Name') or primary.get('courseName') or primary.get('CourseName') or 'No Course'
        return primary, progress, time_spent, display_name

    def _process_single_user(self, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single user and return student data with enrollments.

        Per-thread 401 tolerance (HMG pattern): under heavy parallel fan-out
        (max_workers=50), Absorb's load balancer can return 401 for an
        individual call even with a valid token. Retry that single call
        once before giving up. If retry also fails, return None so the
        batch keeps going instead of one bad call killing every other
        student's data.
        """
        try:
            user_id = user.get('id') or user.get('Id')
            if not user_id:
                return None

            # Get enrollments, with one inline retry on 401 to absorb
            # transient parallel-fan-out hiccups from Absorb's load balancer.
            try:
                enrollments = self.get_user_enrollments(user_id)
            except AbsorbAPIError as _e:
                if _e.status_code == 401:
                    try:
                        enrollments = self.get_user_enrollments(user_id)
                    except AbsorbAPIError:
                        # Still 401 — skip this user, don't kill the batch
                        return None
                else:
                    raise

            # Find primary enrollment (prioritizes Pre-Licensing course)
            primary, calculated_progress, total_time, course_name = self._find_primary_course(enrollments)

            # Calculate exam prep time — main bundle courses only. Per product
            # convention, the main exam prep course name ends with "Exam Prep"
            # (e.g., "Texas Life & Health Exam Prep"). Absorb's parent course
            # timeSpent is an aggregated rollup of its sub-components (walkthrough
            # videos, study guides, practice exams, flashcards, content outlines),
            # which also match the broader is_exam_prep_course test — summing
            # both double-counts. Must stay in sync with routes/students.py.
            _main_prep = 0
            _fallback_sum = 0
            for e in enrollments:
                e_name = e.get('name') or e.get('Name') or e.get('courseName') or e.get('CourseName') or ''
                if not self._is_exam_prep_course(e_name) or self._is_prelicensing_course(e_name):
                    continue
                _min = 0
                for _tf in ('timeSpent', 'TimeSpent', 'ActiveTime', 'activeTime'):
                    _tv = e.get(_tf)
                    if _tv:
                        parsed = parse_time_to_minutes(_tv)
                        if parsed > 0:
                            _min = parsed
                            break
                _name_clean = e_name.lower().strip().rstrip('.').rstrip()
                if _name_clean.endswith('exam prep'):
                    _main_prep += _min
                _fallback_sum += _min
            exam_prep_time = _main_prep if _main_prep > 0 else _fallback_sum

            # Build student data
            return {
                'id': user_id,
                'firstName': user.get('firstName') or user.get('FirstName') or '',
                'lastName': user.get('lastName') or user.get('LastName') or '',
                'emailAddress': user.get('emailAddress') or user.get('EmailAddress') or '',
                'username': user.get('username') or user.get('Username') or '',
                'lastLoginDate': user.get('lastLoginDate') or user.get('LastLoginDate') or user.get('dateLastAccessed') or user.get('DateLastAccessed'),
                'departmentId': user.get('departmentId') or user.get('DepartmentId') or '',
                'departmentName': user.get('departmentName') or user.get('DepartmentName') or '',
                'enrollments': enrollments,
                'primaryEnrollment': primary,
                'progress': calculated_progress,
                'timeSpent': total_time,
                'examPrepTime': exam_prep_time,
                'courseName': course_name,
                'enrollmentStatus': (primary.get('status') or primary.get('Status') or 0) if primary else 0
            }
        except AbsorbAPIError as e:
            # 401 from any deeper call (post-retry) — skip this user, keep batch alive.
            # Non-401 Absorb errors still propagate (caller handles them at the dept level).
            if e.status_code == 401:
                return None
            raise
        except Exception as e:
            print(f"[API] Error processing user: {e}")
            return None

    def get_students_basic(self, department_id: str) -> List[Dict[str, Any]]:
        """Get basic student data WITHOUT enrollments (fast)."""
        users = self.get_users_by_department(department_id)
        print(f"[API] Got {len(users)} users (basic data only)")

        students_data = []
        for user in users:
            user_id = user.get('id') or user.get('Id')
            if not user_id:
                continue
            students_data.append({
                'id': user_id,
                'firstName': user.get('firstName') or user.get('FirstName') or '',
                'lastName': user.get('lastName') or user.get('LastName') or '',
                'emailAddress': user.get('emailAddress') or user.get('EmailAddress') or '',
                'username': user.get('username') or user.get('Username') or '',
                'lastLoginDate': user.get('lastLoginDate') or user.get('LastLoginDate') or user.get('dateLastAccessed') or user.get('DateLastAccessed'),
                'departmentId': user.get('departmentId') or user.get('DepartmentId') or '',
                'departmentName': user.get('departmentName') or user.get('DepartmentName') or '',
                'enrollments': [],
                'primaryEnrollment': None,
                'progress': 0,
                'timeSpent': 0,
                'courseName': 'Loading...',
                'enrollmentStatus': 0
            })
        return students_data

    def get_students_with_progress(self, department_id: str) -> List[Dict[str, Any]]:
        """Get all students in a department with their course progress."""
        users = self.get_users_by_department(department_id)
        total = len(users)

        print(f"[API] Processing {total} students for enrollment data (parallel)...")

        students_data = []
        # Use ThreadPoolExecutor for parallel API calls (max 50 concurrent for I/O-bound operations)
        max_workers = min(50, total) if total > 0 else 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_user = {executor.submit(self._process_single_user, user): user for user in users}

            completed = 0
            failures = 0
            for future in as_completed(future_to_user):
                completed += 1
                try:
                    result = future.result()
                except AbsorbAPIError as e:
                    # Don't let one failed user kill the whole dept fetch.
                    failures += 1
                    if e.status_code != 401:
                        print(f"[API] Non-401 error on a user fetch: {e}")
                    result = None
                except Exception as e:
                    failures += 1
                    print(f"[API] Unexpected error on a user fetch: {e}")
                    result = None
                if result:
                    students_data.append(result)

                # Progress update every 10 students
                if completed % 10 == 0 or completed == total:
                    print(f"[API] Processed {completed}/{total} students...")

        if failures > 0:
            print(f"[API] COMPLETE: {len(students_data)} students with enrollment data ({failures} skipped due to errors)")
        else:
            print(f"[API] COMPLETE: {len(students_data)} students with enrollment data")
        return students_data
