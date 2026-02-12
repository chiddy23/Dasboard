"""Study gap metrics calculator.

Analyzes enrollment dates to find gaps in study activity.
A gap is defined as a period of more than 1 day between consecutive study dates.
"""

from datetime import datetime


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
    """
    if not enrollments:
        return {
            'study_gap_count': 0,
            'total_gap_days': 0,
            'largest_gap_days': 0,
            'last_gap_date': '',
            'study_dates_count': 0,
        }

    all_dates = set()
    for enrollment in enrollments:
        dates = _extract_dates_from_enrollment(enrollment)
        all_dates.update(dates)

    if len(all_dates) < 2:
        return {
            'study_gap_count': 0,
            'total_gap_days': 0,
            'largest_gap_days': 0,
            'last_gap_date': '',
            'study_dates_count': len(all_dates),
        }

    sorted_dates = sorted(all_dates)

    gaps = []
    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i - 1]).days
        if diff > 1:
            gaps.append({
                'days': diff,
                'start': sorted_dates[i - 1],
            })

    if not gaps:
        return {
            'study_gap_count': 0,
            'total_gap_days': 0,
            'largest_gap_days': 0,
            'last_gap_date': '',
            'study_dates_count': len(sorted_dates),
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
    }
