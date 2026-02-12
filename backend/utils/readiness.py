"""Readiness calculator for JustInsurance Student Dashboard.

Evaluates student exam readiness based on 4 criteria:
1. Practice Exams: 3 consecutive scores >= 80% (most recent first)
2. Time in Course: >= 30 hours for Life & Health, >= 20 hours for Life only
3. State Laws: >= 1 completion AND >= 1.5 hours spent
4. Videos: Life courses need Life videos (30+ min), Health needs Health videos, L&H needs both

Status Levels:
- GREEN: All 4 criteria met
- YELLOW: 2+ criteria met (unless exam within 48 hours and not all met)
- RED: 0-1 criteria met, OR exam within 48 hours and not all criteria met
"""

from .formatters import parse_time_spent_to_minutes


# Course name classification helpers
def _is_practice_exam(name):
    """Check if enrollment is a practice exam course."""
    if not name:
        return False
    return 'practice' in name.lower()


def _is_state_law(name):
    """Check if enrollment is a state law course (contains 'law' and/or 'specific')."""
    if not name:
        return False
    lower = name.lower()
    return 'law' in lower or 'specific' in lower


def _is_video_course(name):
    """Check if enrollment is a video course."""
    if not name:
        return False
    return 'video' in name.lower()


def _is_life_video(name):
    """Check if video course is Life-related."""
    if not name:
        return False
    lower = name.lower()
    return 'video' in lower and 'life' in lower


def _is_health_video(name):
    """Check if video course is Health-related."""
    if not name:
        return False
    lower = name.lower()
    return 'video' in lower and 'health' in lower


def _get_enrollment_minutes(enrollment):
    """Extract time spent in minutes from an enrollment."""
    time_val = enrollment.get('timeSpent') or enrollment.get('TimeSpent') or enrollment.get('ActiveTime') or enrollment.get('activeTime') or 0
    return parse_time_spent_to_minutes(time_val)


def _get_enrollment_progress(enrollment):
    """Extract progress (0-100) from an enrollment."""
    progress = enrollment.get('progress') or enrollment.get('Progress') or 0
    try:
        return float(progress)
    except (ValueError, TypeError):
        return 0.0


def _get_enrollment_status(enrollment):
    """Extract status code from an enrollment."""
    status = enrollment.get('status') or enrollment.get('Status') or 0
    try:
        return int(status)
    except (ValueError, TypeError):
        return 0


def _get_enrollment_name(enrollment):
    """Extract course name from an enrollment."""
    return enrollment.get('courseName') or enrollment.get('CourseName') or ''


def _get_enrollment_date(enrollment):
    """Extract a sortable date string from an enrollment (for ordering most recent first)."""
    return (
        enrollment.get('dateCompleted') or enrollment.get('DateCompleted') or
        enrollment.get('dateEdited') or enrollment.get('DateEdited') or
        enrollment.get('dateStarted') or enrollment.get('DateStarted') or
        enrollment.get('dateAdded') or enrollment.get('DateAdded') or ''
    )


def _is_prelicensing(name):
    """Check if course is a pre-licensing course (main course, not modules/chapters)."""
    if not name:
        return False
    lower = name.lower()
    return ('pre-licens' in lower or 'prelicens' in lower or 'pre licens' in lower)


def _course_type_needs_life(course_type):
    """Check if course type requires Life content."""
    if not course_type:
        return True  # Default to requiring both
    lower = course_type.lower()
    return 'life' in lower


def _course_type_needs_health(course_type):
    """Check if course type requires Health content."""
    if not course_type:
        return True  # Default to requiring both
    lower = course_type.lower()
    return 'health' in lower


def calculate_readiness(enrollments, course_type=None, days_until_exam=None):
    """
    Calculate readiness status and detailed breakdown for a student.

    Args:
        enrollments: List of raw Absorb enrollment objects
        course_type: The exam course type from Google Sheet (e.g., "Life & Health", "Life")
        days_until_exam: Number of days until exam (None if unknown)

    Returns:
        dict with status, criteria details, and summary
    """
    # Categorize enrollments
    practice_exams = []
    state_laws = []
    video_courses = []
    prelicensing_courses = []

    for e in enrollments:
        name = _get_enrollment_name(e)
        if _is_practice_exam(name):
            practice_exams.append(e)
        if _is_state_law(name):
            state_laws.append(e)
        if _is_video_course(name):
            video_courses.append(e)
        if _is_prelicensing(name):
            prelicensing_courses.append(e)

    # --- Criterion 1: Practice Exams ---
    # Sort by most recent date first
    practice_exams.sort(key=lambda e: _get_enrollment_date(e), reverse=True)
    practice_scores = [_get_enrollment_progress(e) for e in practice_exams]
    practice_total_minutes = sum(_get_enrollment_minutes(e) for e in practice_exams)
    practice_total_hours = practice_total_minutes / 60.0
    # Build detail list: name, score, time, date for each attempt
    practice_details = []
    for e in practice_exams:
        practice_details.append({
            'name': _get_enrollment_name(e),
            'score': _get_enrollment_progress(e),
            'minutes': round(_get_enrollment_minutes(e), 1),
            'date': _get_enrollment_date(e),
            'status': _get_enrollment_status(e)
        })
    consecutive_passing = 0
    for score in practice_scores:
        if score >= 80:
            consecutive_passing += 1
        else:
            break
    practice_met = consecutive_passing >= 3

    # --- Criterion 2: Time in Course ---
    total_course_minutes = sum(_get_enrollment_minutes(e) for e in prelicensing_courses)
    total_course_hours = total_course_minutes / 60.0

    needs_life = _course_type_needs_life(course_type)
    needs_health = _course_type_needs_health(course_type)
    is_life_and_health = needs_life and needs_health

    required_hours = 30 if is_life_and_health else 20
    time_met = total_course_hours >= required_hours

    # --- Criterion 3: State Laws ---
    law_completions = sum(1 for e in state_laws if _get_enrollment_status(e) in (2, 3))
    law_total_minutes = sum(_get_enrollment_minutes(e) for e in state_laws)
    law_total_hours = law_total_minutes / 60.0
    laws_met = law_completions >= 1 and law_total_hours >= 1.5

    # --- Criterion 4: Videos ---
    life_video_minutes = sum(
        _get_enrollment_minutes(e) for e in video_courses
        if _is_life_video(_get_enrollment_name(e))
    )
    health_video_minutes = sum(
        _get_enrollment_minutes(e) for e in video_courses
        if _is_health_video(_get_enrollment_name(e))
    )

    videos_met = True
    video_details = {}
    if needs_life:
        life_ok = life_video_minutes >= 30
        video_details['life'] = {
            'required': True,
            'minutes': life_video_minutes,
            'met': life_ok
        }
        if not life_ok:
            videos_met = False
    if needs_health:
        health_ok = health_video_minutes >= 30
        video_details['health'] = {
            'required': True,
            'minutes': health_video_minutes,
            'met': health_ok
        }
        if not health_ok:
            videos_met = False

    # --- Calculate status ---
    criteria_met = sum([practice_met, time_met, laws_met, videos_met])

    if criteria_met == 4:
        status = 'GREEN'
    elif criteria_met >= 2:
        # Yellow unless exam within 48 hours
        if days_until_exam is not None and days_until_exam <= 2 and criteria_met < 4:
            status = 'RED'
        else:
            status = 'YELLOW'
    else:
        status = 'RED'

    return {
        'status': status,
        'criteriaMet': criteria_met,
        'criteriaTotal': 4,
        'criteria': {
            'practiceExams': {
                'met': practice_met,
                'label': 'Practice Exams',
                'requirement': '3 consecutive scores >= 80%',
                'consecutivePassing': consecutive_passing,
                'scores': practice_scores[:5],  # Show up to 5 most recent
                'totalExams': len(practice_exams),
                'hoursSpent': round(practice_total_hours, 1),
                'attempts': practice_details[:10]  # Up to 10 most recent attempts
            },
            'timeInCourse': {
                'met': time_met,
                'label': 'Time in Course',
                'requirement': f'>= {required_hours} hours',
                'hoursLogged': round(total_course_hours, 1),
                'hoursRequired': required_hours,
                'courseType': course_type or 'Unknown'
            },
            'stateLaws': {
                'met': laws_met,
                'label': 'State Laws',
                'requirement': '>= 1 completion AND >= 1.5 hours',
                'completions': law_completions,
                'hoursSpent': round(law_total_hours, 1),
                'totalCourses': len(state_laws)
            },
            'videos': {
                'met': videos_met,
                'label': 'Videos',
                'requirement': '30+ min per required type',
                'details': video_details,
                'totalCourses': len(video_courses)
            }
        }
    }
