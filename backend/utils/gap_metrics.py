"""Study gap metrics calculator.

Analyzes enrollment dates to find gaps in study activity.
A gap is defined as a period of more than 1 day between consecutive study dates.
"""

from datetime import datetime, timedelta


def _extract_dates_from_enrollment(enrollment):
    """Extract all available date fields from a single enrollment as date objects."""
    date_fields = [
        'dateStarted', 'DateStarted',
        'dateEdited', 'DateEdited',
        'accessDate', 'AccessDate',
        'dateCompleted', 'DateCompleted',
        'dateAdded', 'DateAdded',
    ]
    dates = []
    for field in date_fields:
        val = enrollment.get(field)
        if not val or not isinstance(val, str):
            continue
        try:
            # Handle ISO format with timezone suffix
            clean = val.replace('Z', '').split('+')[0].split('.')[0]
            dt = datetime.fromisoformat(clean)
            dates.append(dt.date())
        except (ValueError, AttributeError):
            continue
    return dates


def _build_timeline(sorted_dates, gaps):
    """Build alternating study/gap timeline from sorted dates and gap list.

    Returns list of {type: 'study'|'gap', start: 'YYYY-MM-DD', end: 'YYYY-MM-DD', days: N}
    in chronological order.
    """
    if not sorted_dates:
        return []

    # Build a set of gap start dates for quick lookup
    # gap 'start' is the last study day before the gap
    gap_map = {}
    for g in gaps:
        gap_map[g['start']] = g['days']

    timeline = []
    study_start = sorted_dates[0]
    study_end = sorted_dates[0]

    for i in range(1, len(sorted_dates)):
        prev = sorted_dates[i - 1]
        curr = sorted_dates[i]
        diff = (curr - prev).days

        if diff > 1:
            # End the current study period
            timeline.append({
                'type': 'study',
                'start': study_start.isoformat(),
                'end': prev.isoformat(),
                'days': (prev - study_start).days + 1,
            })
            # Add the gap (day after last study → day before next study)
            gap_start = prev + timedelta(days=1)
            gap_end = curr - timedelta(days=1)
            timeline.append({
                'type': 'gap',
                'start': gap_start.isoformat(),
                'end': gap_end.isoformat(),
                'days': (gap_end - gap_start).days + 1,
            })
            # Start new study period
            study_start = curr

        study_end = curr

    # Final study period
    timeline.append({
        'type': 'study',
        'start': study_start.isoformat(),
        'end': study_end.isoformat(),
        'days': (study_end - study_start).days + 1,
    })

    return timeline


def calculate_gap_metrics(enrollments):
    """
    Calculate study gap metrics from ALL enrollments.

    Collects every date field from every enrollment, deduplicates to unique
    calendar days, then finds gaps > 1 day between consecutive study dates.

    Args:
        enrollments: List of raw Absorb enrollment objects

    Returns:
        dict with:
            - study_gap_count: number of gaps > 1 day
            - total_gap_days: sum of all gap days
            - largest_gap_days: the biggest single gap
            - last_gap_date: ISO date string of the most recent gap start
            - study_dates_count: total unique study dates found
            - timeline: list of alternating study/gap periods with date ranges
    """
    empty = {
        'study_gap_count': 0,
        'total_gap_days': 0,
        'largest_gap_days': 0,
        'last_gap_date': '',
        'study_dates_count': 0,
        'timeline': [],
    }

    if not enrollments:
        return empty

    all_dates = set()
    for enrollment in enrollments:
        dates = _extract_dates_from_enrollment(enrollment)
        all_dates.update(dates)

    if len(all_dates) < 2:
        return {**empty, 'study_dates_count': len(all_dates)}

    sorted_dates = sorted(all_dates)

    gaps = []
    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i - 1]).days
        if diff > 1:
            gaps.append({
                'days': diff,
                'start': sorted_dates[i - 1],
            })

    timeline = _build_timeline(sorted_dates, gaps)

    if not gaps:
        return {
            'study_gap_count': 0,
            'total_gap_days': 0,
            'largest_gap_days': 0,
            'last_gap_date': '',
            'study_dates_count': len(sorted_dates),
            'timeline': timeline,
        }

    total_gap_days = sum(g['days'] for g in gaps)
    largest_gap = max(gaps, key=lambda g: g['days'])
    last_gap = gaps[-1]  # Chronological order

    return {
        'study_gap_count': len(gaps),
        'total_gap_days': total_gap_days,
        'largest_gap_days': largest_gap['days'],
        'last_gap_date': last_gap['start'].isoformat(),
        'study_dates_count': len(sorted_dates),
        'timeline': timeline,
    }
