"""Additional edge-case tests for MCP_Server/validation.py.

Supplements the baseline coverage in test_validation.py with boundary
conditions, degenerate inputs, and algorithmic property checks for
_reduce_automation_points and _validate_notes.
"""

import math
import pytest
from MCP_Server.validation import (
    _validate_notes,
    _validate_automation_points,
    _reduce_automation_points,
    _validate_index,
    _validate_range,
    MAX_NOTES_PER_CALL,
    MAX_AUTOMATION_POINTS,
)


# ---------------------------------------------------------------------------
# _reduce_automation_points edge cases
# ---------------------------------------------------------------------------

class TestReduceAutomationPointsEdgeCases:

    def test_single_point_returned_as_is(self):
        """A single point should be returned unchanged."""
        pts = [{"time": 0.0, "value": 0.5}]
        result = _reduce_automation_points(pts)
        assert len(result) == 1
        assert result[0]["time"] == 0.0
        assert result[0]["value"] == 0.5

    def test_two_points_returned_as_is(self):
        """Two points should be returned unchanged (min for meaningful reduction)."""
        pts = [{"time": 0.0, "value": 0.0}, {"time": 1.0, "value": 1.0}]
        result = _reduce_automation_points(pts)
        assert len(result) == 2

    def test_all_same_time_deduped(self):
        """Points at the same time should be deduplicated to one (last wins)."""
        pts = [
            {"time": 0.0, "value": 0.1},
            {"time": 0.0, "value": 0.5},
            {"time": 0.0, "value": 0.9},
        ]
        result = _reduce_automation_points(pts)
        assert len(result) == 1
        # Last value at that time should win
        assert result[0]["value"] == 0.9

    def test_exactly_max_points(self):
        """When count equals max_points, output should not exceed max_points."""
        pts = [{"time": float(i), "value": float(i % 5) / 5.0} for i in range(20)]
        result = _reduce_automation_points(pts, max_points=20)
        assert len(result) <= 20

    def test_preserves_first_and_last(self):
        """Reduction should always preserve the first and last points."""
        pts = [{"time": float(i), "value": float(i % 3) / 3.0} for i in range(50)]
        result = _reduce_automation_points(pts, max_points=5)
        assert result[0]["time"] == pts[0]["time"]
        assert result[-1]["time"] == pts[-1]["time"]

    def test_step_function_preserves_transitions(self):
        """Step-like changes should preserve transition points."""
        pts = [
            {"time": 0.0, "value": 0.0},
            {"time": 1.0, "value": 0.0},
            {"time": 1.001, "value": 1.0},
            {"time": 2.0, "value": 1.0},
            {"time": 2.001, "value": 0.0},
            {"time": 3.0, "value": 0.0},
        ]
        result = _reduce_automation_points(pts, max_points=20)
        values = [p["value"] for p in result]
        assert 0.0 in values
        assert 1.0 in values

    def test_large_reduction(self):
        """Reducing 500 points to 10 should work without error and respect limit."""
        pts = [{"time": float(i), "value": math.sin(i * 0.1)} for i in range(500)]
        result = _reduce_automation_points(pts, max_points=10)
        assert len(result) <= 10
        assert len(result) >= 2  # at minimum first and last

    def test_collinear_points_removed(self):
        """Three collinear points should reduce to two."""
        pts = [
            {"time": 0.0, "value": 0.0},
            {"time": 5.0, "value": 5.0},
            {"time": 10.0, "value": 10.0},
        ]
        result = _reduce_automation_points(pts, max_points=100)
        assert len(result) == 2  # middle point is collinear, removed

    def test_non_collinear_points_preserved(self):
        """Points that form a V-shape should all be preserved."""
        pts = [
            {"time": 0.0, "value": 0.0},
            {"time": 5.0, "value": 10.0},
            {"time": 10.0, "value": 0.0},
        ]
        result = _reduce_automation_points(pts, max_points=100)
        assert len(result) == 3

    def test_monotonic_ascending_values(self):
        """Monotonically ascending values on a line should reduce heavily."""
        pts = [{"time": float(i), "value": float(i)} for i in range(100)]
        result = _reduce_automation_points(pts, max_points=50)
        # Should keep just first and last (all collinear)
        assert len(result) <= 3

    def test_zigzag_pattern_preserves_peaks(self):
        """Zigzag (sawtooth) pattern should preserve peak/valley points."""
        pts = []
        for i in range(20):
            pts.append({"time": float(i), "value": float(i % 2)})
        result = _reduce_automation_points(pts, max_points=20)
        values = {p["value"] for p in result}
        assert 0.0 in values
        assert 1.0 in values

    def test_very_close_times_deduped(self):
        """Points closer than time_epsilon should be deduplicated."""
        pts = [
            {"time": 0.0, "value": 0.0},
            {"time": 0.0005, "value": 0.5},  # within default epsilon of 0.001
            {"time": 1.0, "value": 1.0},
        ]
        result = _reduce_automation_points(pts)
        assert len(result) == 2

    def test_output_sorted_by_time(self):
        """Result should always be sorted by time regardless of input order."""
        pts = [
            {"time": 5.0, "value": 0.5},
            {"time": 0.0, "value": 0.0},
            {"time": 10.0, "value": 1.0},
            {"time": 2.5, "value": 0.25},
        ]
        result = _reduce_automation_points(pts, max_points=10)
        times = [p["time"] for p in result]
        assert times == sorted(times)

    def test_constant_value_reduces_to_two(self):
        """Points with the same value at different times should reduce to 2."""
        pts = [{"time": float(i), "value": 0.5} for i in range(50)]
        result = _reduce_automation_points(pts, max_points=50)
        assert len(result) == 2  # all collinear (horizontal line)


# ---------------------------------------------------------------------------
# _validate_notes edge cases
# ---------------------------------------------------------------------------

class TestValidateNotesEdgeCases:

    def test_float_pitch_raises(self):
        """Float pitch should be rejected (pitch must be integer)."""
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{
                "pitch": 60.5, "start_time": 0.0, "duration": 1.0, "velocity": 100
            }])

    def test_boolean_pitch_raises(self):
        """Boolean pitch should be rejected (booleans are excluded)."""
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{
                "pitch": True, "start_time": 0.0, "duration": 1.0, "velocity": 100
            }])

    def test_boolean_velocity_raises(self):
        """Boolean velocity should be rejected."""
        with pytest.raises(ValueError, match="velocity must be"):
            _validate_notes([{
                "pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": True
            }])

    def test_boolean_duration_raises(self):
        """Boolean duration should be rejected."""
        with pytest.raises(ValueError, match="duration must be"):
            _validate_notes([{
                "pitch": 60, "start_time": 0.0, "duration": True, "velocity": 100
            }])

    def test_boolean_start_time_raises(self):
        """Boolean start_time should be rejected."""
        with pytest.raises(ValueError, match="start_time must be"):
            _validate_notes([{
                "pitch": 60, "start_time": False, "duration": 1.0, "velocity": 100
            }])

    def test_boundary_pitch_zero(self):
        """Pitch 0 (lowest MIDI note) should be valid."""
        _validate_notes([{
            "pitch": 0, "start_time": 0.0, "duration": 1.0, "velocity": 64
        }])

    def test_boundary_pitch_127(self):
        """Pitch 127 (highest MIDI note) should be valid."""
        _validate_notes([{
            "pitch": 127, "start_time": 0.0, "duration": 1.0, "velocity": 64
        }])

    def test_boundary_velocity_zero(self):
        """Velocity 0 (note-off) should be valid per the implementation."""
        _validate_notes([{
            "pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 0
        }])

    def test_boundary_velocity_127(self):
        """Velocity 127 (maximum) should be valid."""
        _validate_notes([{
            "pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 127
        }])

    def test_very_small_duration_valid(self):
        """Very small but positive duration should be valid."""
        _validate_notes([{
            "pitch": 60, "start_time": 0.0, "duration": 0.001, "velocity": 100
        }])

    def test_large_start_time_valid(self):
        """Large start_time should be valid (no upper bound)."""
        _validate_notes([{
            "pitch": 60, "start_time": 10000.0, "duration": 1.0, "velocity": 100
        }])

    def test_start_time_zero_valid(self):
        """start_time of exactly 0 should be valid."""
        _validate_notes([{
            "pitch": 60, "start_time": 0, "duration": 1.0, "velocity": 100
        }])

    def test_float_velocity_valid(self):
        """Float velocity in range should be valid (impl accepts int|float)."""
        _validate_notes([{
            "pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 64.5
        }])

    def test_string_pitch_raises(self):
        """String pitch should be rejected."""
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{
                "pitch": "60", "start_time": 0.0, "duration": 1.0, "velocity": 100
            }])

    def test_none_value_raises(self):
        """None as a note dict value should be rejected."""
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{
                "pitch": None, "start_time": 0.0, "duration": 1.0, "velocity": 100
            }])

    def test_note_is_not_dict_raises(self):
        """Note that is not a dict should raise."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            _validate_notes(["not a dict"])

    def test_not_a_list_raises(self):
        """Passing a dict instead of a list should raise."""
        with pytest.raises(ValueError, match="must be a list"):
            _validate_notes({"pitch": 60, "start_time": 0.0,
                             "duration": 1.0, "velocity": 100})

    def test_multiple_notes_with_one_invalid(self):
        """Validation should fail if any note in the list is invalid."""
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([
                {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
                {"pitch": 200, "start_time": 1.0, "duration": 1.0, "velocity": 100},
            ])

    def test_extra_keys_allowed(self):
        """Notes with extra keys beyond required should still be valid."""
        _validate_notes([{
            "pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100,
            "mute": False, "probability": 0.8,
        }])

    def test_exactly_max_notes_valid(self):
        """Exactly MAX_NOTES_PER_CALL notes should be valid."""
        notes = [{"pitch": 60, "start_time": float(i), "duration": 1.0, "velocity": 100}
                 for i in range(MAX_NOTES_PER_CALL)]
        _validate_notes(notes)  # should not raise

    def test_one_over_max_notes_raises(self):
        """MAX_NOTES_PER_CALL + 1 notes should raise."""
        notes = [{"pitch": 60, "start_time": float(i), "duration": 1.0, "velocity": 100}
                 for i in range(MAX_NOTES_PER_CALL + 1)]
        with pytest.raises(ValueError, match="Too many notes"):
            _validate_notes(notes)


# ---------------------------------------------------------------------------
# _validate_automation_points edge cases
# ---------------------------------------------------------------------------

class TestValidateAutomationPointsEdgeCases:

    def test_boolean_time_raises(self):
        """Boolean time value should be rejected."""
        with pytest.raises(ValueError, match="time must be"):
            _validate_automation_points([{"time": True, "value": 0.5}])

    def test_boolean_value_raises(self):
        """Boolean value should be rejected."""
        with pytest.raises(ValueError, match="value must be"):
            _validate_automation_points([{"time": 0.0, "value": False}])

    def test_negative_value_allowed(self):
        """Negative values should be allowed (automation may go negative)."""
        _validate_automation_points([{"time": 0.0, "value": -1.0}])

    def test_large_value_allowed(self):
        """Large values should be allowed (no upper bound on value)."""
        _validate_automation_points([{"time": 0.0, "value": 999999.0}])

    def test_zero_time_valid(self):
        """Time of exactly 0.0 should be valid."""
        _validate_automation_points([{"time": 0.0, "value": 0.5}])

    def test_not_a_dict_raises(self):
        """Automation point that is not a dict should raise."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            _validate_automation_points([42])

    def test_string_time_raises(self):
        """String time should be rejected."""
        with pytest.raises(ValueError, match="time must be"):
            _validate_automation_points([{"time": "0.0", "value": 0.5}])

    def test_exactly_max_points_valid(self):
        """Exactly MAX_AUTOMATION_POINTS should be valid."""
        pts = [{"time": float(i), "value": 0.5} for i in range(MAX_AUTOMATION_POINTS)]
        _validate_automation_points(pts)  # should not raise


# ---------------------------------------------------------------------------
# _validate_index edge cases
# ---------------------------------------------------------------------------

class TestValidateIndexEdgeCases:

    def test_zero_is_valid(self):
        """Zero should be a valid index."""
        _validate_index(0, "test")

    def test_large_positive_valid(self):
        """Very large positive integer should be valid."""
        _validate_index(999999, "test")

    def test_none_raises(self):
        """None should be rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_index(None, "test")

    def test_list_raises(self):
        """List should be rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_index([0], "test")


# ---------------------------------------------------------------------------
# _validate_range edge cases
# ---------------------------------------------------------------------------

class TestValidateRangeEdgeCases:

    def test_exactly_at_min_boundary(self):
        """Value exactly at min boundary should be valid."""
        _validate_range(0.0, "test", 0.0, 1.0)

    def test_exactly_at_max_boundary(self):
        """Value exactly at max boundary should be valid."""
        _validate_range(1.0, "test", 0.0, 1.0)

    def test_none_raises(self):
        """None should be rejected as non-numeric."""
        with pytest.raises(ValueError, match="must be a number"):
            _validate_range(None, "test", 0.0, 1.0)

    def test_string_raises(self):
        """String should be rejected as non-numeric."""
        with pytest.raises(ValueError, match="must be a number"):
            _validate_range("0.5", "test", 0.0, 1.0)

    def test_negative_range(self):
        """Negative range bounds should work correctly."""
        _validate_range(-0.5, "test", -1.0, 0.0)

    def test_integer_within_float_range(self):
        """Integer value within a float range should be accepted."""
        _validate_range(0, "test", -1.0, 1.0)
