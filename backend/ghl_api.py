"""GoHighLevel (GHL) Calendar API client for exam scheduling data."""

import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

GHL_BASE_URL = 'https://services.leadconnectorhq.com'
GHL_API_VERSION = '2021-07-28'

# Per-user cache: {user_email: {'data': [...], 'timestamp': datetime}}
_ghl_cache = {}
GHL_CACHE_TTL = 300  # 5 minutes


def _ghl_headers(token):
    """Build GHL API request headers."""
    return {
        'Authorization': f'Bearer {token}',
        'Version': GHL_API_VERSION,
        'Accept': 'application/json',
    }


def fetch_ghl_calendars(token, location_id):
    """Fetch available calendars for a GHL location.

    Returns list of {id, name} dicts for the setup dropdown.
    """
    url = f'{GHL_BASE_URL}/calendars/'
    params = {'locationId': location_id}
    resp = requests.get(url, headers=_ghl_headers(token), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    calendars = data.get('calendars', [])
    return [{'id': c.get('id', ''), 'name': c.get('name', 'Unnamed')} for c in calendars]


def _fetch_contact(token, contact_id, location_id):
    """Fetch a single contact's details from GHL."""
    url = f'{GHL_BASE_URL}/contacts/{contact_id}'
    try:
        resp = requests.get(url, headers=_ghl_headers(token), params={'locationId': location_id}, timeout=10)
        resp.raise_for_status()
        contact = resp.json().get('contact', {})
        return {
            'id': contact_id,
            'email': (contact.get('email') or '').lower().strip(),
            'name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
            'phone': contact.get('phone') or '',
        }
    except Exception as e:
        print(f"[GHL] Failed to fetch contact {contact_id}: {e}")
        return {'id': contact_id, 'email': '', 'name': '', 'phone': ''}


def fetch_ghl_appointments(token, location_id, calendar_id, user_email):
    """Fetch GHL calendar appointments and return in same format as fetch_exam_sheet().

    Looks 3 months back and 6 months forward from today.
    Deduplicates by contact email (last occurrence wins).
    Caches per user_email with 5-minute TTL.
    """
    # Check cache
    now = datetime.utcnow()
    cache_key = user_email.lower().strip()
    if cache_key in _ghl_cache:
        entry = _ghl_cache[cache_key]
        age = (now - entry['timestamp']).total_seconds()
        if age < GHL_CACHE_TTL:
            print(f"[GHL] Using cached data for {cache_key} (age: {int(age)}s)")
            return entry['data']

    print(f"[GHL] Fetching appointments for calendar {calendar_id}...")

    # Date range: 3 months back, 6 months forward (epoch milliseconds for GHL API)
    import calendar as _cal
    start_dt = now - timedelta(days=90)
    end_dt = now + timedelta(days=180)
    start_time = int(_cal.timegm(start_dt.timetuple())) * 1000
    end_time = int(_cal.timegm(end_dt.timetuple())) * 1000

    # Fetch appointments (paginated)
    all_appointments = []
    url = f'{GHL_BASE_URL}/calendars/events'
    params = {
        'locationId': location_id,
        'calendarId': calendar_id,
        'startTime': start_time,
        'endTime': end_time,
    }

    print(f"[GHL] Request URL: {url}")
    print(f"[GHL] Request params: {params}")
    resp = requests.get(url, headers=_ghl_headers(token), params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    print(f"[GHL] Response keys: {list(data.keys())}")
    print(f"[GHL] Response preview: {str(data)[:500]}")
    events = data.get('events', data.get('data', data.get('appointments', [])))
    all_appointments.extend(events)
    print(f"[GHL] Fetched {len(all_appointments)} appointments")

    if not all_appointments:
        _ghl_cache[cache_key] = {'data': [], 'timestamp': now}
        return []

    # Collect unique contact IDs
    contact_ids = set()
    for appt in all_appointments:
        cid = appt.get('contactId')
        if cid:
            contact_ids.add(cid)

    print(f"[GHL] Fetching {len(contact_ids)} unique contacts...")

    # Parallel contact lookups
    contact_map = {}
    if contact_ids:
        max_workers = min(10, len(contact_ids))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_contact, token, cid, location_id): cid for cid in contact_ids}
            for future in as_completed(futures):
                result = future.result()
                if result and result.get('email'):
                    contact_map[result['id']] = result

    # Transform appointments into sheet-format dicts
    students = []
    for appt in all_appointments:
        cid = appt.get('contactId')
        contact = contact_map.get(cid, {})

        email = contact.get('email', '')
        if not email:
            continue

        # Parse appointment start time
        start_str = appt.get('startTime') or appt.get('start') or ''
        exam_date = ''
        exam_date_formatted = 'TBD'
        exam_time = ''

        if start_str:
            try:
                dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                exam_date = f"{dt.month}/{dt.day}/{dt.year}"
                exam_date_formatted = dt.strftime('%b %d, %Y')
                hour = dt.hour % 12 or 12
                am_pm = 'AM' if dt.hour < 12 else 'PM'
                exam_time = f"{hour}:{dt.minute:02d} {am_pm}"
            except Exception:
                pass

        students.append({
            'name': contact.get('name', ''),
            'email': email,
            'phone': contact.get('phone', ''),
            'examDate': exam_date,
            'examDateFormatted': exam_date_formatted,
            'examTime': exam_time,
            'state': '',
            'course': '',
            'agencyOwner': '',
            'passFail': '',
            'finalOutcome': '',
            'alertDate': '',
            'studyHoursAtExam': '',
            'finalPractice': '',
            'chaptersComplete': '',
            'videosWatched': '',
            'stateLawsDone': '',
            'studyConsistency': '',
            't0Sent': '',
            'weeklyTracking': [],
        })

    # Dedup by email (last occurrence wins)
    seen = {}
    for s in students:
        seen[s['email']] = s
    students = list(seen.values())

    print(f"[GHL] Processed {len(students)} unique students from GHL")

    _ghl_cache[cache_key] = {'data': students, 'timestamp': now}
    return students


def invalidate_ghl_cache(user_email):
    """Clear GHL cache for a specific user."""
    cache_key = user_email.lower().strip()
    if cache_key in _ghl_cache:
        del _ghl_cache[cache_key]
        print(f"[GHL] Cache invalidated for {cache_key}")
