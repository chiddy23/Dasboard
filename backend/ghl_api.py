"""GoHighLevel (GHL) Calendar API client for exam scheduling data."""

import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

GHL_BASE_URL = 'https://services.leadconnectorhq.com'
GHL_API_VERSION = '2021-07-28'

# Per-user cache: {user_email: {'data': [...], 'timestamp': datetime}}
_ghl_cache = {}
GHL_CACHE_TTL = 300  # 5 minutes

# Reverse lookup: {contact_email: {contact_id, appointment_id, calendar_id}}
_ghl_id_map = {}


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
        if resp.status_code == 401:
            print(f"[GHL] Contact 401 body: {resp.text[:300]}")
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
    # Log full first appointment to see all available fields
    if data.get('events') and len(data['events']) > 0:
        print(f"[GHL] First appointment FULL: {data['events'][0]}")
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

    if contact_ids and not contact_map:
        print("[GHL] WARNING: All contact lookups failed! Token likely missing 'contacts.readonly' scope."
              " Go to GHL > Settings > Integrations > Private Integrations > edit your app > enable Contacts scope.")

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

    # Dedup by email (last occurrence wins) and build ID map for write-backs
    seen = {}
    for s in students:
        seen[s['email']] = s
    students = list(seen.values())

    # Build reverse lookup for write-backs (email → GHL IDs)
    for appt in all_appointments:
        cid = appt.get('contactId')
        contact = contact_map.get(cid, {})
        cemail = contact.get('email', '')
        if cemail:
            _ghl_id_map[cemail] = {
                'contact_id': cid,
                'appointment_id': appt.get('id', ''),
                'calendar_id': appt.get('calendarId', calendar_id),
                'assigned_user_id': appt.get('assignedUserId', ''),
            }

    print(f"[GHL] Processed {len(students)} unique students from GHL")

    _ghl_cache[cache_key] = {'data': students, 'timestamp': now}
    return students


def get_ghl_ids(email):
    """Look up GHL contact/appointment IDs for an email.

    Returns dict with contact_id, appointment_id, calendar_id or None.
    """
    return _ghl_id_map.get(email.lower().strip())


def update_ghl_contact(token, contact_id, location_id, name='', email='', phone=''):
    """Update a GHL contact's name, email, and/or phone.

    Returns True on success, False on failure.
    """
    url = f'{GHL_BASE_URL}/contacts/{contact_id}'
    body = {}
    if name:
        parts = name.strip().split(' ', 1)
        body['firstName'] = parts[0]
        body['lastName'] = parts[1] if len(parts) > 1 else ''
    if email:
        body['email'] = email
    if phone:
        body['phone'] = phone

    if not body:
        return False

    try:
        headers = _ghl_headers(token)
        headers['Content-Type'] = 'application/json'
        resp = requests.put(url, headers=headers, json=body,
                            params={'locationId': location_id}, timeout=10)
        resp.raise_for_status()
        print(f"[GHL] Updated contact {contact_id}: {body}")

        # Update ID map if email changed
        if email:
            old_entries = {k: v for k, v in _ghl_id_map.items() if v.get('contact_id') == contact_id}
            for old_email in old_entries:
                entry = _ghl_id_map.pop(old_email)
                _ghl_id_map[email.lower().strip()] = entry

        return True
    except Exception as e:
        print(f"[GHL] Failed to update contact {contact_id}: {e}")
        return False


def update_ghl_appointment(token, appointment_id, calendar_id, location_id,
                           start_time_iso='', end_time_iso='',
                           assigned_user_id=''):
    """Update a GHL appointment's start/end time.

    Times should be ISO 8601 format (e.g. '2026-03-15T14:00:00-05:00').
    Returns True on success, False on failure.
    """
    url = f'{GHL_BASE_URL}/calendars/events/appointments/{appointment_id}'
    body = {
        'calendarId': calendar_id,
        'locationId': location_id,
        'ignoreFreeSlotValidation': True,
        'ignoreDateRange': True,
    }
    if assigned_user_id:
        body['assignedUserId'] = assigned_user_id
    if start_time_iso:
        body['startTime'] = start_time_iso
    if end_time_iso:
        body['endTime'] = end_time_iso

    if not start_time_iso and not end_time_iso:
        return False

    try:
        headers = _ghl_headers(token)
        headers['Content-Type'] = 'application/json'
        print(f"[GHL] Updating appointment {appointment_id}, body: {body}")
        resp = requests.put(url, headers=headers, json=body, timeout=10)
        if resp.status_code != 200:
            print(f"[GHL] Appointment update {resp.status_code} body: {resp.text[:500]}")
        resp.raise_for_status()
        print(f"[GHL] Updated appointment {appointment_id}: {start_time_iso}")
        return True
    except Exception as e:
        print(f"[GHL] Failed to update appointment {appointment_id}: {e}")
        return False


def invalidate_ghl_cache(user_email):
    """Clear GHL cache for a specific user."""
    cache_key = user_email.lower().strip()
    if cache_key in _ghl_cache:
        del _ghl_cache[cache_key]
        print(f"[GHL] Cache invalidated for {cache_key}")
