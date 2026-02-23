import pytest
from MCP_Server.validation import (
    _validate_index, _validate_index_allow_negative, _validate_range,
    _validate_notes, _validate_automation_points,
    _reduce_automation_points,
    MAX_NOTES_PER_CALL, MAX_AUTOMATION_POINTS,
)


class TestValidateIndex:
    def test_valid_zero(self):
        _validate_index(0, "test")  # should not raise

    def test_valid_positive(self):
        _validate_index(100, "test")  # should not raise

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            _validate_index(-1, "test")

    def test_float_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_index(1.5, "test")

    def test_bool_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_index(True, "test")

    def test_string_raises(self):
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_index("0", "test")


class TestValidateIndexAllowNegative:
    def test_minus_one_default(self):
        _validate_index_allow_negative(-1, "test")  # should not raise

    def test_below_min_raises(self):
        with pytest.raises(ValueError, match=">= -1"):
            _validate_index_allow_negative(-2, "test")

    def test_custom_min(self):
        _validate_index_allow_negative(-5, "test", min_value=-5)

    def test_below_custom_min_raises(self):
        with pytest.raises(ValueError):
            _validate_index_allow_negative(-6, "test", min_value=-5)


class TestValidateRange:
    def test_valid_middle(self):
        _validate_range(0.5, "test", 0.0, 1.0)

    def test_valid_min_bound(self):
        _validate_range(0.0, "test", 0.0, 1.0)

    def test_valid_max_bound(self):
        _validate_range(1.0, "test", 0.0, 1.0)

    def test_below_min_raises(self):
        with pytest.raises(ValueError, match="between"):
            _validate_range(-0.1, "test", 0.0, 1.0)

    def test_above_max_raises(self):
        with pytest.raises(ValueError, match="between"):
            _validate_range(1.1, "test", 0.0, 1.0)

    def test_bool_raises(self):
        with pytest.raises(ValueError, match="must be a number"):
            _validate_range(True, "test", 0.0, 1.0)

    def test_int_in_float_range(self):
        _validate_range(1, "test", 0.0, 1.0)  # int should work for float range


class TestValidateNotes:
    def test_valid_single_note(self):
        _validate_notes([{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}])

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_notes([])

    def test_not_list_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            _validate_notes("not a list")

    def test_too_many_notes_raises(self):
        notes = [{"pitch": 60, "start_time": float(i), "duration": 1.0, "velocity": 100}
                 for i in range(MAX_NOTES_PER_CALL + 1)]
        with pytest.raises(ValueError, match="Too many notes"):
            _validate_notes(notes)

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing required keys"):
            _validate_notes([{"pitch": 60, "start_time": 0.0}])  # missing duration, velocity

    def test_invalid_pitch_raises(self):
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{"pitch": 128, "start_time": 0.0, "duration": 1.0, "velocity": 100}])

    def test_negative_pitch_raises(self):
        with pytest.raises(ValueError, match="pitch must be"):
            _validate_notes([{"pitch": -1, "start_time": 0.0, "duration": 1.0, "velocity": 100}])

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError, match="duration must be"):
            _validate_notes([{"pitch": 60, "start_time": 0.0, "duration": -1.0, "velocity": 100}])

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError, match="duration must be"):
            _validate_notes([{"pitch": 60, "start_time": 0.0, "duration": 0.0, "velocity": 100}])

    def test_negative_start_time_raises(self):
        with pytest.raises(ValueError, match="start_time must be"):
            _validate_notes([{"pitch": 60, "start_time": -1.0, "duration": 1.0, "velocity": 100}])

    def test_velocity_out_of_range_raises(self):
        with pytest.raises(ValueError, match="velocity must be"):
            _validate_notes([{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 200}])


class TestValidateAutomationPoints:
    def test_valid_points(self):
        _validate_automation_points([{"time": 0.0, "value": 0.5}, {"time": 1.0, "value": 0.8}])

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_automation_points([])

    def test_too_many_raises(self):
        points = [{"time": float(i), "value": 0.5} for i in range(MAX_AUTOMATION_POINTS + 1)]
        with pytest.raises(ValueError, match="Too many"):
            _validate_automation_points(points)

    def test_missing_keys_raises(self):
        with pytest.raises(ValueError, match="must have"):
            _validate_automation_points([{"time": 0.0}])

    def test_negative_time_raises(self):
        with pytest.raises(ValueError, match="time must be"):
            _validate_automation_points([{"time": -1.0, "value": 0.5}])


class TestReduceAutomationPoints:
    def test_two_points_unchanged(self):
        pts = [{"time": 0.0, "value": 0.0}, {"time": 1.0, "value": 1.0}]
        result = _reduce_automation_points(pts)
        assert len(result) == 2

    def test_collinear_points_reduced(self):
        # 5 points on a straight line should reduce to 2
        pts = [{"time": float(i), "value": float(i)} for i in range(5)]
        result = _reduce_automation_points(pts, max_points=20)
        assert len(result) <= 3  # first + last, maybe one more

    def test_max_points_respected(self):
        # 100 random-ish points
        pts = [{"time": float(i), "value": float(i % 10) / 10.0} for i in range(100)]
        result = _reduce_automation_points(pts, max_points=10)
        assert len(result) <= 10

    def test_duplicate_times_deduped(self):
        pts = [
            {"time": 0.0, "value": 0.0},
            {"time": 0.0, "value": 0.5},
            {"time": 1.0, "value": 1.0},
        ]
        result = _reduce_automation_points(pts)
        assert len(result) == 2  # deduped to first=0.5, last=1.0
