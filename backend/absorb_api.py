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
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('enrollments') or data.get('Enrollments') or []
        except Exception as e:
            # Try alternate casing as fallback
            try:
                url = f"{self.base_url}/Users/{user_id}/Enrollments"
                response = self._session.get(url, params=params, headers=self._get_headers(), timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get('enrollments') or data.get('Enrollments') or []
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

        # Debug: Log first enrollment's time-related keys
        first = enrollments[0]
        time_keys = [k for k in first.keys() if 'time' in k.lower()]
        if time_keys:
            print(f"[API DEBUG] Time keys found: {time_keys}")
            for k in time_keys:
                print(f"[API DEBUG]   {k} = {first.get(k)}")

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
            # Calculate average progress across all Pre-Licensing enrollments
            valid_progress = []
            total_time = 0
            for e in all_prelicensing:
                # Handle progress (might be string or number)
                prog = e.get('progress') or e.get('Progress') or 0
                try:
                    prog = float(prog) if prog else 0
                    valid_progress.append(prog)
                except (ValueError, TypeError):
                    pass

                # Handle time spent (might be HH:MM:SS string or number)
                time_val = e.get('timeSpent') or e.get('TimeSpent') or e.get('ActiveTime') or e.get('activeTime') or 0
                total_time += parse_time_to_minutes(time_val)

            if valid_progress:
                avg_progress = sum(valid_progress) / len(valid_progress)
            else:
                avg_progress = 0

            # Determine display name
            if prelicensing_main:
                display_name = prelicensing_main.get('courseName') or prelicensing_main.get('CourseName') or 'Pre-License Course'
            else:
                display_name = 'Pre-License Course'

            primary = prelicensing_main or all_prelicensing[0]
            return primary, avg_progress, total_time, display_name

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

            # Build student data
            return {
                'id': user_id,
                'firstName': user.get('firstName') or user.get('FirstName') or '',
                'lastName': user.get('lastName') or user.get('LastName') or '',
                'emailAddress': user.get('emailAddress') or user.get('EmailAddress') or '',
                'username': user.get('username') or user.get('Username') or '',
                'lastLoginDate': user.get('lastLoginDate') or user.get('LastLoginDate') or user.get('dateLastAccessed') or user.get('DateLastAccessed'),
                'enrollments': enrollments,
                'primaryEnrollment': primary,
                'progress': calculated_progress,
                'timeSpent': total_time,
                'courseName': course_name,
                'enrollmentStatus': (primary.get('status') or primary.get('Status') or 0) if primary else 0
            }
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
