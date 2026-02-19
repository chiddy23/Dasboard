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
    """Parse time value to minutes. Handles HH:MM:SS.microseconds string or numeric values."""
    if not time_value:
        return 0
    if isinstance(time_value, (int, float)):
        return int(time_value)
    if isinstance(time_value, str):
        try:
            time_part = time_value.split('.')[0]
            parts = time_part.split(':')
            if len(parts) == 3:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
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
        """Get headers for API requests."""
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if include_auth and self._token:
            # Note: Absorb API accepts token directly without "Bearer" prefix
            headers['Authorization'] = self._token
        return headers

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
                raise AbsorbAPIError("Session expired. Please log in again.", 401)

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
        """Get users in a specific department using OData filter (matches Apps Script pattern)."""
        url = f"{self.base_url}/users"
        all_users = []
        offset = 0
        limit = 500  # Match Apps Script batch size

        print(f"[API] Fetching users for department: {department_id} (OData filter)")

        while True:
            # Use exact OData filter syntax from working Apps Script
            params = {
                "_filter": f"departmentId eq guid'{department_id}'",
                "_limit": limit,
                "_offset": offset
            }

            response = self._session.get(url, params=params, headers=self._get_headers(), timeout=120)

            if response.status_code == 401:
                print(f"[API] Token expired - need to re-authenticate")
                raise AbsorbAPIError("Session expired. Please log in again.", 401)

            if response.status_code != 200:
                print(f"[API] Users fetch failed at offset {offset}: {response.status_code} - {response.text}")
                break

            data = response.json()

            # Handle response format
            if isinstance(data, dict) and 'users' in data:
                users = data['users']
            elif isinstance(data, list):
                users = data
            else:
                print(f"[API] Unexpected response format")
                break

            if not users:
                print(f"[API] No more users found at offset {offset}")
                break

            # Trust the OData filter - it returns users in this department AND sub-departments
            all_users.extend(users)
            print(f"[API] Fetched {len(users)} users (total: {len(all_users)})")

            # Check if we've fetched all users
            if len(users) < limit:
                print(f"[API] Reached end of users list")
                break

            offset += limit

        print(f"[API] COMPLETE: Found {len(all_users)} students in department {department_id}")
        return all_users

    def get_department(self, department_id: str) -> Dict[str, Any]:
        """Get department information."""
        url = f"{self.base_url}/Departments/{department_id}"
        response = self._session.get(url, headers=self._get_headers(), timeout=30)

        if response.status_code == 200:
            return response.json()
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

    def _is_prelicensing_course(self, course_name: str) -> bool:
        """Check if a course is a Pre-Licensing/Pre-License course."""
        if not course_name:
            return False
        name_lower = course_name.lower()
        # Match "pre-license", "pre-licensing", "prelicense", "prelicensing", etc.
        return ('pre-licens' in name_lower or
                'prelicens' in name_lower or
                'pre licens' in name_lower)

    def _is_exam_prep_course(self, course_name: str) -> bool:
        """Check if a course is an Exam Prep course."""
        if not course_name:
            return False
        name_lower = course_name.lower()
        return ('practice' in name_lower or
                'prep' in name_lower or
                'study' in name_lower)

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
            course_name = e.get('courseName') or e.get('CourseName') or ''
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
            time_val = primary.get('timeSpent') or primary.get('TimeSpent') or primary.get('ActiveTime') or primary.get('activeTime') or 0
            main_time = parse_time_to_minutes(time_val)

            # Log when main course has 0 time to diagnose root cause
            if main_time == 0:
                cname = primary.get('courseName') or primary.get('CourseName') or ''
                time_fields = {k: v for k, v in primary.items() if 'time' in k.lower() or 'active' in k.lower() or 'duration' in k.lower() or 'spent' in k.lower()}
                print(f"[TIME DEBUG] Main course '{cname}' reports 0 time. Raw time fields: {time_fields}")
                print(f"[TIME DEBUG] All enrollment keys: {list(primary.keys())}")

            # Determine display name
            if prelicensing_main:
                display_name = prelicensing_main.get('courseName') or prelicensing_main.get('CourseName') or 'Pre-License Course'
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

        # Handle time spent (might be HH:MM:SS string or number)
        time_spent = primary.get('timeSpent') or primary.get('TimeSpent') or primary.get('ActiveTime') or primary.get('activeTime') or 0
        time_spent = parse_time_to_minutes(time_spent)

        display_name = primary.get('courseName') or primary.get('CourseName') or 'No Course'
        return primary, progress, time_spent, display_name

    def _process_single_user(self, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single user and return student data with enrollments."""
        try:
            user_id = user.get('id') or user.get('Id')
            if not user_id:
                return None

            # Get enrollments
            enrollments = self.get_user_enrollments(user_id)

            # Find primary enrollment (prioritizes Pre-Licensing course)
            primary, calculated_progress, total_time, course_name = self._find_primary_course(enrollments)

            # Calculate exam prep time (combined time from all exam prep courses)
            exam_prep_time = 0
            for e in enrollments:
                e_name = e.get('courseName') or e.get('CourseName') or ''
                if self._is_exam_prep_course(e_name):
                    time_val = e.get('timeSpent') or e.get('TimeSpent') or e.get('ActiveTime') or e.get('activeTime') or 0
                    exam_prep_time += parse_time_to_minutes(time_val)

            # Build student data
            return {
                'id': user_id,
                'firstName': user.get('firstName') or user.get('FirstName') or '',
                'lastName': user.get('lastName') or user.get('LastName') or '',
                'emailAddress': user.get('emailAddress') or user.get('EmailAddress') or '',
                'username': user.get('username') or user.get('Username') or '',
                'lastLoginDate': user.get('lastLoginDate') or user.get('LastLoginDate') or user.get('dateLastAccessed') or user.get('DateLastAccessed'),
                'departmentId': user.get('departmentId') or user.get('DepartmentId') or '',
                'enrollments': enrollments,
                'primaryEnrollment': primary,
                'progress': calculated_progress,
                'timeSpent': total_time,
                'examPrepTime': exam_prep_time,
                'courseName': course_name,
                'enrollmentStatus': (primary.get('status') or primary.get('Status') or 0) if primary else 0
            }
        except AbsorbAPIError:
            raise  # Propagate auth errors (401)
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
            for future in as_completed(future_to_user):
                completed += 1
                result = future.result()
                if result:
                    students_data.append(result)

                # Progress update every 10 students
                if completed % 10 == 0 or completed == total:
                    print(f"[API] Processed {completed}/{total} students...")

        print(f"[API] COMPLETE: {len(students_data)} students with enrollment data")
        return students_data
