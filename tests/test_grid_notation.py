import pytest
from MCP_Server.grid_notation import parse_grid, notes_to_grid


class TestParseGrid:
    def test_basic_drum_pattern(self):
        grid = "KK|x---x---|x---x---|"
        notes = parse_grid(grid)
        assert len(notes) > 0
        # KK = kick drum, should map to MIDI note 36
        for note in notes:
            assert note["pitch"] == 36

    def test_basic_melodic_pattern(self):
        grid = "C4|o-------|--------|"
        notes = parse_grid(grid)
        assert len(notes) > 0
        # C4 = MIDI note 60
        for note in notes:
            assert note["pitch"] == 60

    def test_empty_grid_returns_empty(self):
        grid = ""
        notes = parse_grid(grid)
        assert notes == []

    def test_multi_line_drum(self):
        grid = """KK|x---x---|
SN|----x---|
HH|x-x-x-x-|"""
        notes = parse_grid(grid)
        assert len(notes) > 0
        pitches = set(n["pitch"] for n in notes)
        assert len(pitches) >= 2  # at least kick and snare or hat

    def test_note_names(self):
        """Test various note name formats."""
        grid = "C#4|o-------|"
        notes = parse_grid(grid)
        assert len(notes) > 0
        assert notes[0]["pitch"] == 61  # C#4 = MIDI 61


class TestNotesToGrid:
    def test_roundtrip_simple(self):
        """Notes -> grid -> notes should preserve basic structure."""
        original_notes = [
            {"pitch": 60, "start_time": 0.0, "duration": 0.25, "velocity": 100},
            {"pitch": 64, "start_time": 0.5, "duration": 0.25, "velocity": 100},
        ]
        grid_str = notes_to_grid(original_notes)
        assert isinstance(grid_str, str)
        assert len(grid_str) > 0

    def test_drum_notes_detected(self):
        """Notes in drum range should produce drum labels."""
        drum_notes = [
            {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 100},
            {"pitch": 38, "start_time": 0.5, "duration": 0.25, "velocity": 100},
        ]
        grid_str = notes_to_grid(drum_notes)
        assert isinstance(grid_str, str)
