"""Bitrix24 CRM API client for exam scheduling data."""

import requests
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Per-user cache: {user_email: {'data': [...], 'timestamp': datetime}}
_bitrix_cache = {}
BITRIX_CACHE_TTL = 300  # 5 minutes

# Reverse lookup: {contact_email: {contact_id, activity_id, owner_id}}
_bitrix_id_map = {}


def parse_webhook_url(webhook_url):
    """Parse a Bitrix24 inbound webhook URL into components.

    URL format: https://domain.bitrix24.com/rest/user_id/secret/
    Returns: {'domain': '...', 'user_id': '...', 'secret': '...', 'base_url': '...'}
    """
    url = webhook_url.rstrip('/')
    parsed = urlparse(url)
    parts = parsed.path.strip('/').split('/')

    if len(parts) < 3 or parts[0] != 'rest':
        raise ValueError(f"Invalid Bitrix24 webhook URL format: {webhook_url}")

    return {
        'domain': parsed.netloc,
        'user_id': parts[1],
        'secret': parts[2],
        'base_url': f"https://{parsed.netloc}/rest/{parts[1]}/{parts[2]}",
    }


def _bitrix_call(webhook_url, method, params=None, timeout=15):
    """Make a Bitrix24 REST API call.

    All Bitrix API calls use POST with the method name in the URL path.
    Returns the parsed JSON response.
    """
    parsed = parse_webhook_url(webhook_url)
    url = f"{parsed['base_url']}/{method}.json"
    resp = requests.post(url, json=params or {}, timeout=timeout)
    if resp.status_code == 503:
        print(f"[BITRIX] Rate limited on {method}, retrying after 1s...")
        time.sleep(1)
        resp = requests.post(url, json=params or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _bitrix_batch(webhook_url, commands, timeout=30):
    """Execute a batch of up to 50 Bitrix API calls in a single request.

    commands: dict of {label: "method?param=value&param2=value2"}
    Returns: dict of {label: result}
    """
    parsed = parse_webhook_url(webhook_url)
    url = f"{parsed['base_url']}/batch.json"
    resp = requests.post(url, json={'halt': 0, 'cmd': commands}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get('result', {}).get('result', {})


def validate_webhook(webhook_url):
    """Validate a Bitrix24 webhook URL by making a lightweight API call.

    Returns: {'valid': True, 'user_name': '...'} or {'valid': False, 'error': '...'}
    """
    try:
        parsed = parse_webhook_url(webhook_url)
        data = _bitrix_call(webhook_url, 'profile', timeout=10)
        result = data.get('result', {})
        name = f"{result.get('NAME', '')} {result.get('LAST_NAME', '')}".strip()
        return {
            'valid': True,
            'user_id': parsed['user_id'],
            'user_name': name or f"User {parsed['user_id']}",
            'domain': parsed['domain'],
        }
    except ValueError as e:
        return {'valid': False, 'error': str(e)}
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 401:
            return {'valid': False, 'error': 'Invalid webhook URL or secret'}
        return {'valid': False, 'error': f'Bitrix API error ({status})'}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def _parse_contact_email(contact):
    """Extract the first email from a Bitrix contact's multi-value EMAIL field."""
    emails = contact.get('EMAIL', [])
    if isinstance(emails, list) and emails:
        return (emails[0].get('VALUE', '') or '').lower().strip()
    return ''


def _parse_contact_phone(contact):
    """Extract the first phone from a Bitrix contact's multi-value PHONE field."""
    phones = contact.get('PHONE', [])
    if isinstance(phones, list) and phones:
        return phones[0].get('VALUE', '') or ''
    return ''


def _parse_contact_name(contact):
    """Build full name from Bitrix contact NAME + LAST_NAME fields."""
    first = contact.get('NAME', '') or ''
    last = contact.get('LAST_NAME', '') or ''
    return f"{first} {last}".strip()


def fetch_bitrix_activities(webhook_url, user_email):
    """Fetch Bitrix24 CRM activities and return in same format as fetch_exam_sheet().

    Looks 3 months back and 6 months forward from today.
    Deduplicates by contact email (last occurrence wins).
    Caches per user_email with 5-minute TTL.
    """
    # Check cache
    now = datetime.utcnow()
    cache_key = user_email.lower().strip()
    if cache_key in _bitrix_cache:
        entry = _bitrix_cache[cache_key]
        age = (now - entry['timestamp']).total_seconds()
        if age < BITRIX_CACHE_TTL:
            print(f"[BITRIX] Using cached data for {cache_key} (age: {int(age)}s)")
            return entry['data']

    print(f"[BITRIX] Fetching CRM activities for {cache_key}...")

    # Date range: 3 months back, 6 months forward
    start_dt = now - timedelta(days=90)
    end_dt = now + timedelta(days=180)
    start_str = start_dt.strftime('%Y-%m-%dT00:00:00')
    end_str = end_dt.strftime('%Y-%m-%dT23:59:59')

    # Parse webhook to get responsible user ID
    parsed = parse_webhook_url(webhook_url)
    responsible_id = parsed['user_id']

    # Fetch activities (paginated, 50 per page)
    all_activities = []
    start = 0
    while True:
        try:
            data = _bitrix_call(webhook_url, 'crm.activity.list', {
                'filter': {
                    'RESPONSIBLE_ID': responsible_id,
                    '>=START_TIME': start_str,
                    '<=END_TIME': end_str,
                },
                'select': [
                    'ID', 'SUBJECT', 'START_TIME', 'END_TIME',
                    'OWNER_TYPE_ID', 'OWNER_ID', 'RESPONSIBLE_ID',
                    'COMPLETED', 'COMMUNICATIONS',
                ],
                'order': {'START_TIME': 'ASC'},
                'start': start,
            })
        except Exception as e:
            print(f"[BITRIX] Error fetching activities (start={start}): {e}")
            break

        result = data.get('result', [])
        all_activities.extend(result)
        print(f"[BITRIX] Fetched {len(result)} activities (total: {len(all_activities)})")

        if 'next' in data:
            start = data['next']
        else:
            break

    print(f"[BITRIX] Total activities fetched: {len(all_activities)}")

    if not all_activities:
        _bitrix_cache[cache_key] = {'data': [], 'timestamp': now}
        return []

    # Collect unique contact IDs (OWNER_TYPE_ID=3 means Contact)
    contact_ids = set()
    for act in all_activities:
        owner_type = str(act.get('OWNER_TYPE_ID', ''))
        owner_id = act.get('OWNER_ID')
        if owner_type == '3' and owner_id:
            contact_ids.add(str(owner_id))

    # Also check COMMUNICATIONS for contact emails as fallback
    # (some activities link to deals/leads but have contact communications)

    print(f"[BITRIX] Resolving {len(contact_ids)} unique contacts...")

    # Batch contact resolution (50 per batch call to respect rate limits)
    contact_map = {}  # {contact_id: {name, email, phone}}
    contact_id_list = list(contact_ids)

    for batch_start in range(0, len(contact_id_list), 50):
        batch_ids = contact_id_list[batch_start:batch_start + 50]
        commands = {}
        for cid in batch_ids:
            commands[f'contact_{cid}'] = f'crm.contact.get?ID={cid}'

        try:
            results = _bitrix_batch(webhook_url, commands)
            for cid in batch_ids:
                key = f'contact_{cid}'
                contact_data = results.get(key, {})
                if contact_data:
                    email = _parse_contact_email(contact_data)
                    if email:
                        contact_map[cid] = {
                            'id': cid,
                            'email': email,
                            'name': _parse_contact_name(contact_data),
                            'phone': _parse_contact_phone(contact_data),
                            'raw': contact_data,
                        }
        except Exception as e:
            print(f"[BITRIX] Batch contact fetch error: {e}")

        # Brief pause between batches if more than one
        if batch_start + 50 < len(contact_id_list):
            time.sleep(0.5)

    if contact_ids and not contact_map:
        print("[BITRIX] WARNING: All contact lookups failed! Check webhook permissions (crm scope required).")

    # Transform activities into sheet-format dicts
    students = []
    for act in all_activities:
        owner_type = str(act.get('OWNER_TYPE_ID', ''))
        owner_id = str(act.get('OWNER_ID', ''))

        # Get contact from owner or communications
        contact = contact_map.get(owner_id, {})
        email = contact.get('email', '')

        # Fallback: check COMMUNICATIONS field for email
        if not email:
            comms = act.get('COMMUNICATIONS', [])
            if isinstance(comms, list):
                for comm in comms:
                    val = (comm.get('VALUE', '') or '').lower().strip()
                    if '@' in val:
                        email = val
                        break

        if not email:
            continue

        # Parse activity start time
        start_str = act.get('START_TIME', '')
        exam_date = ''
        exam_date_formatted = 'TBD'
        exam_time = ''

        if start_str:
            try:
                # Bitrix returns datetime like "2026-03-15T14:00:00+00:00"
                dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                exam_date = f"{dt.month}/{dt.day}/{dt.year}"
                exam_date_formatted = dt.strftime('%b %d, %Y')
                hour = dt.hour % 12 or 12
                am_pm = 'AM' if dt.hour < 12 else 'PM'
                exam_time = f"{hour}:{dt.minute:02d} {am_pm}"
            except Exception:
                pass

        students.append({
            'name': contact.get('name', '') or act.get('SUBJECT', ''),
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

    # Build reverse lookup for write-backs (email → Bitrix IDs)
    for act in all_activities:
        owner_type = str(act.get('OWNER_TYPE_ID', ''))
        owner_id = str(act.get('OWNER_ID', ''))
        contact = contact_map.get(owner_id, {})
        cemail = contact.get('email', '')

        # Fallback to communications
        if not cemail:
            comms = act.get('COMMUNICATIONS', [])
            if isinstance(comms, list):
                for comm in comms:
                    val = (comm.get('VALUE', '') or '').lower().strip()
                    if '@' in val:
                        cemail = val
                        break

        if cemail:
            _bitrix_id_map[cemail] = {
                'contact_id': owner_id if owner_type == '3' else '',
                'activity_id': str(act.get('ID', '')),
                'owner_type_id': owner_type,
                'owner_id': owner_id,
                'responsible_id': str(act.get('RESPONSIBLE_ID', '')),
            }

    print(f"[BITRIX] Processed {len(students)} unique students from Bitrix")

    _bitrix_cache[cache_key] = {'data': students, 'timestamp': now}
    return students


def get_bitrix_ids(email):
    """Look up Bitrix contact/activity IDs for an email.

    Returns dict with contact_id, activity_id, etc. or None.
    """
    return _bitrix_id_map.get(email.lower().strip())


def update_bitrix_contact(webhook_url, contact_id, name='', email='', phone=''):
    """Update a Bitrix24 CRM contact's name, email, and/or phone.

    Returns True on success, False on failure.
    """
    if not contact_id:
        return False

    fields = {}
    if name:
        parts = name.strip().split(' ', 1)
        fields['NAME'] = parts[0]
        fields['LAST_NAME'] = parts[1] if len(parts) > 1 else ''

    # For email/phone multi-value fields, fetch existing to get field IDs
    if email or phone:
        try:
            data = _bitrix_call(webhook_url, 'crm.contact.get', {'ID': contact_id})
            existing = data.get('result', {})

            if email:
                existing_emails = existing.get('EMAIL', [])
                if existing_emails and isinstance(existing_emails, list):
                    # Update first existing email
                    fields['EMAIL'] = [{'ID': existing_emails[0].get('ID'), 'VALUE': email, 'VALUE_TYPE': 'EMAIL'}]
                else:
                    # Add new email
                    fields['EMAIL'] = [{'VALUE': email, 'VALUE_TYPE': 'EMAIL'}]

            if phone:
                existing_phones = existing.get('PHONE', [])
                if existing_phones and isinstance(existing_phones, list):
                    # Update first existing phone
                    fields['PHONE'] = [{'ID': existing_phones[0].get('ID'), 'VALUE': phone, 'VALUE_TYPE': 'MOBILE'}]
                else:
                    # Add new phone
                    fields['PHONE'] = [{'VALUE': phone, 'VALUE_TYPE': 'MOBILE'}]
        except Exception as e:
            print(f"[BITRIX] Error fetching contact {contact_id} for update: {e}")
            # Proceed with simple add if fetch fails
            if email:
                fields['EMAIL'] = [{'VALUE': email, 'VALUE_TYPE': 'EMAIL'}]
            if phone:
                fields['PHONE'] = [{'VALUE': phone, 'VALUE_TYPE': 'MOBILE'}]

    if not fields:
        return False

    try:
        _bitrix_call(webhook_url, 'crm.contact.update', {
            'ID': contact_id,
            'FIELDS': fields,
        })
        print(f"[BITRIX] Updated contact {contact_id}: {list(fields.keys())}")

        # Update ID map if email changed
        if email:
            old_entries = {k: v for k, v in _bitrix_id_map.items() if v.get('contact_id') == contact_id}
            for old_email in old_entries:
                entry = _bitrix_id_map.pop(old_email)
                _bitrix_id_map[email.lower().strip()] = entry

        return True
    except Exception as e:
        print(f"[BITRIX] Failed to update contact {contact_id}: {e}")
        return False


def update_bitrix_activity(webhook_url, activity_id, start_time='', end_time=''):
    """Update a Bitrix24 CRM activity's start/end time.

    Times should be ISO 8601 format (e.g. '2026-03-15T14:00:00').
    No slot validation needed (unlike GHL).
    Returns True on success, False on failure.
    """
    if not start_time and not end_time:
        return False

    fields = {}
    if start_time:
        fields['START_TIME'] = start_time
    if end_time:
        fields['END_TIME'] = end_time

    try:
        print(f"[BITRIX] Updating activity {activity_id}, fields: {fields}")
        _bitrix_call(webhook_url, 'crm.activity.update', {
            'ID': activity_id,
            'FIELDS': fields,
        })
        print(f"[BITRIX] Updated activity {activity_id}: {start_time}")
        return True
    except Exception as e:
        print(f"[BITRIX] Failed to update activity {activity_id}: {e}")
        return False


def invalidate_bitrix_cache(user_email):
    """Clear Bitrix cache for a specific user."""
    cache_key = user_email.lower().strip()
    if cache_key in _bitrix_cache:
        del _bitrix_cache[cache_key]
        print(f"[BITRIX] Cache invalidated for {cache_key}")
