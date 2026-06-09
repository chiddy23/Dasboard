"""
Tests for the dual-LOA combined-status fix.

Covers three layers of the fix introduced so that a student enrolled in
SEPARATE Life and Health pre-license courses (e.g. Ohio, Michigan) sees a
single consistent status on both the list view and the detail modal:

  1. The pure helper ``derive_combined_status`` (absorb_api) — exercises all
     five priority rules of the status-derivation table.
  2. ``calculate_prelicensing_totals`` (routes.students) — the modal path that
     was previously overwriting ``primary_status`` on every iteration and
     ended up showing "X% progress + Not Started" when the not-started course
     happened to be last in Absorb's response.
  3. ``AbsorbAPIClient._find_primary_course`` (absorb_api) — the list-view path
     that shares the same derivation helper so the two surfaces agree.

Run from the backend directory:

    python -m unittest discover -s backend/tests -p test_*.py -v
"""

import os
import sys
import unittest

# Ensure ``backend/`` is on sys.path so ``from absorb_api import ...`` and
# ``from routes.students import ...`` resolve when the tests are discovered
# from either the backend dir or the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from absorb_api import AbsorbAPIClient, derive_combined_status  # noqa: E402
from routes.students import calculate_prelicensing_totals  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enrollment(
    *,
    course_id,
    name,
    status,
    progress,
    time_spent="00:00:00",
    enrollment_id=None,
):
    """Build a synthetic enrollment dict modeled on the audit shape.

    Matches the shape returned by the Absorb API:
        {"id", "courseId", "name", "progress", "timeSpent", "status",
         "score", "dateAdded", "dateStarted", "dateEdited", "dateCompleted",
         "accessDate", "courseName"}
    """
    return {
        "id": enrollment_id or f"e-{course_id}",
        "courseId": course_id,
        "name": name,
        "progress": progress,
        "timeSpent": time_spent,
        "status": status,
        "score": None,
        "dateAdded": "2026-01-15T10:00:00",
        "dateStarted": "2026-01-16T09:00:00",
        "dateEdited": "2026-03-04T14:30:00",
        "dateCompleted": None,
        "accessDate": "2026-03-04T14:30:00",
        "courseName": name,
    }


# ---------------------------------------------------------------------------
# Section 1: Unit tests for derive_combined_status
# ---------------------------------------------------------------------------

class DeriveCombinedStatusTests(unittest.TestCase):
    """Pure-function tests of the 5-rule combined-status derivation."""

    def test_r1_any_expired_wins(self):
        """R1: any main Expired (4) short-circuits to Expired."""
        result = derive_combined_status([4, 1], [0.0, 60.0], 30.0)
        self.assertEqual(result, 4)

    def test_r2_all_complete_rounds_under_100(self):
        """R2: all mains Complete (2/3) -> Complete even when avg is 99.9% (rounding)."""
        result = derive_combined_status([2, 2], [100.0, 99.8], 99.9)
        self.assertEqual(result, 2)

    def test_r3_progress_at_or_above_100(self):
        """R3: combined progress >= 100 -> Complete."""
        result = derive_combined_status([1, 1], [100.0, 100.0], 100.0)
        self.assertEqual(result, 2)

    def test_r4_in_progress_combined_progress_above_zero(self):
        """R4 (the Ohio screenshot case): combined progress > 0 -> In Progress."""
        result = derive_combined_status([0, 1], [0.0, 20.0], 10.0)
        self.assertEqual(result, 1)

    def test_r4_in_progress_any_main_in_progress(self):
        """R4: any main with status In Progress (1) -> In Progress."""
        result = derive_combined_status([1, 0], [0.0, 0.0], 0.0)
        self.assertEqual(result, 1)

    def test_r4_in_progress_chapter_lag(self):
        """R4: status=0 but progress>0 (chapter lag) -> In Progress."""
        result = derive_combined_status([0, 0], [5.0, 0.0], 2.5)
        self.assertEqual(result, 1)

    def test_r5_not_started(self):
        """R5: no signal at all -> Not Started."""
        result = derive_combined_status([0, 0], [0.0, 0.0], 0.0)
        self.assertEqual(result, 0)

    def test_single_loa_passthrough_in_progress(self):
        """Single-LOA In Progress passes through unchanged."""
        result = derive_combined_status([1], [35.0], 35.0)
        self.assertEqual(result, 1)

    def test_single_loa_passthrough_complete(self):
        """Single-LOA Complete passes through unchanged."""
        result = derive_combined_status([2], [100.0], 100.0)
        self.assertEqual(result, 2)

    def test_empty_lists(self):
        """No mains at all -> Not Started (safe default)."""
        result = derive_combined_status([], [], 0.0)
        self.assertEqual(result, 0)

    def test_mix_complete_and_not_started(self):
        """Mix of Complete + Not Started -> In Progress (combined progress > 0)."""
        result = derive_combined_status([2, 0], [100.0, 0.0], 50.0)
        self.assertEqual(result, 1)


# ---------------------------------------------------------------------------
# Section 2: Modal-path integration tests for calculate_prelicensing_totals
# ---------------------------------------------------------------------------

class CalculatePrelicensingTotalsTests(unittest.TestCase):
    """Integration tests for the modal-path totals/status calculator."""

    def test_ohio_dual_loa_screenshot_case(self):
        """Ohio Life (Not Started) + Ohio Health (In Progress 20%) -> In Progress.

        Regression for the screenshot bug where status was being overwritten
        on every iteration and the modal showed "10% + Not Started" whenever
        the not-started course was last in Absorb's response.
        """
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=0,
                progress=0,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=1,
                progress=20,
            ),
        ]
        _time, _progress, course_name, primary_status = calculate_prelicensing_totals(enrollments)
        self.assertEqual(primary_status, 1, "dual-LOA must derive In Progress not Not Started")
        self.assertIn("Life & Health", course_name)

    def test_single_loa(self):
        """Single Florida Life pre-license course -> In Progress, name unchanged."""
        enrollments = [
            _enrollment(
                course_id="fl-life",
                name="Florida Life Pre-license Course",
                status=1,
                progress=50,
            ),
        ]
        _time, _progress, course_name, primary_status = calculate_prelicensing_totals(enrollments)
        self.assertEqual(primary_status, 1)
        self.assertEqual(course_name, "Florida Life Pre-license Course")

    def test_both_complete(self):
        """Dual-LOA both Complete (status 2, 100%) -> Complete."""
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=2,
                progress=100,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=2,
                progress=100,
            ),
        ]
        _time, _progress, _name, primary_status = calculate_prelicensing_totals(enrollments)
        self.assertEqual(primary_status, 2)

    def test_one_expired(self):
        """Dual-LOA with one Expired (R1) -> Expired regardless of other progress."""
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=4,
                progress=0,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=1,
                progress=60,
            ),
        ]
        _time, _progress, _name, primary_status = calculate_prelicensing_totals(enrollments)
        self.assertEqual(primary_status, 4)

    def test_no_enrollments(self):
        """Empty enrollment list -> Not Started."""
        _time, _progress, _name, primary_status = calculate_prelicensing_totals([])
        self.assertEqual(primary_status, 0)


# ---------------------------------------------------------------------------
# Section 3: List-view-path integration tests for _find_primary_course
# ---------------------------------------------------------------------------

class FindPrimaryCourseTests(unittest.TestCase):
    """Integration tests for AbsorbAPIClient._find_primary_course (list view)."""

    @classmethod
    def setUpClass(cls):
        # Audit confirmed AbsorbAPIClient() instantiates without network I/O.
        cls.client = AbsorbAPIClient()

    def test_ohio_dual_loa_screenshot_case(self):
        """Same dual-LOA Ohio shape as Section 2 -> derived_status == 1."""
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=0,
                progress=0,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=1,
                progress=20,
            ),
        ]
        result = self.client._find_primary_course(enrollments)
        self.assertEqual(len(result), 5)
        _primary, _progress, _time, _name, derived_status = result
        self.assertEqual(derived_status, 1)

    def test_single_loa_in_progress(self):
        """Single Life pre-license course -> derived_status == 1."""
        enrollments = [
            _enrollment(
                course_id="fl-life",
                name="Florida Life Pre-license Course",
                status=1,
                progress=50,
            ),
        ]
        _primary, _progress, _time, _name, derived_status = self.client._find_primary_course(enrollments)
        self.assertEqual(derived_status, 1)

    def test_both_complete(self):
        """Dual-LOA both Complete -> derived_status == 2."""
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=2,
                progress=100,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=2,
                progress=100,
            ),
        ]
        _primary, _progress, _time, _name, derived_status = self.client._find_primary_course(enrollments)
        self.assertEqual(derived_status, 2)

    def test_one_expired(self):
        """Dual-LOA with one Expired -> derived_status == 4."""
        enrollments = [
            _enrollment(
                course_id="oh-life",
                name="Ohio Life Pre-license Course",
                status=4,
                progress=0,
            ),
            _enrollment(
                course_id="oh-health",
                name="Ohio Health Pre-license Course",
                status=1,
                progress=60,
            ),
        ]
        _primary, _progress, _time, _name, derived_status = self.client._find_primary_course(enrollments)
        self.assertEqual(derived_status, 4)

    def test_no_enrollments(self):
        """Empty list returns the documented sentinel 5-tuple."""
        result = self.client._find_primary_course([])
        self.assertEqual(result, (None, 0, 0, "No Course", 0))

    def test_tuple_arity(self):
        """Return arity must remain 5 — guards against future regressions."""
        self.assertEqual(len(self.client._find_primary_course([])), 5)


if __name__ == "__main__":
    unittest.main()
