"""Tests for MCP_Server/tools/creative.py — creative / generative MIDI tools.

Since the tool functions are nested inside register_tools(mcp), we test them
in two complementary ways:

1. **Pure-logic tests** verify musical algorithms (Euclidean rhythms, scale
   intervals, chord voicings, drum pattern structures) without touching the
   MCP framework at all.

2. **Integration-style tests** register the tools on a disposable FastMCP
   instance, invoke them via the _tool_handler async wrapper, and assert on
   the mocked send_command calls that reach the Ableton connection.
"""

import json
import math
import pytest
from unittest.mock import MagicMock, patch
import MCP_Server.state as state


# ---------------------------------------------------------------------------
# Pure-logic: Euclidean rhythm algorithm
# ---------------------------------------------------------------------------

class TestEuclideanRhythm:
    """Verify the Bjorklund algorithm produces mathematically correct patterns.

    Reference patterns come from Toussaint (2005), "The Euclidean Algorithm
    Generates Traditional Musical Rhythms."
    """

    @staticmethod
    def _bjorklund(steps, pulses):
        """Reference implementation of Bjorklund's algorithm for comparison."""
        if pulses == 0:
            return [0] * steps
        if pulses >= steps:
            return [1] * steps

        groups = [[1] for _ in range(pulses)] + [[0] for _ in range(steps - pulses)]
        while True:
            remainder = len(groups) - pulses
            if remainder <= 1:
                break
            new_groups = []
            take = min(pulses, remainder)
            for i in range(take):
                new_groups.append(groups[i] + groups[pulses + i])
            for i in range(take, pulses):
                new_groups.append(groups[i])
            for i in range(pulses + take, len(groups)):
                new_groups.append(groups[i])
            groups = new_groups
            pulses = take if take < pulses else pulses

        pattern = []
        for g in groups:
            pattern.extend(g)
        return pattern

    def test_tresillo(self):
        """E(3,8) should produce the tresillo rhythm with 3 hits in 8 steps."""
        result = self._bjorklund(8, 3)
        assert sum(result) == 3
        assert len(result) == 8

    def test_cinquillo(self):
        """E(5,8) should produce the cinquillo rhythm with 5 hits in 8 steps."""
        result = self._bjorklund(8, 5)
        assert sum(result) == 5
        assert len(result) == 8

    def test_all_pulses(self):
        """E(n,n) should produce all hits."""
        result = self._bjorklund(4, 4)
        assert result == [1, 1, 1, 1]

    def test_no_pulses(self):
        """E(n,0) should produce all rests."""
        result = self._bjorklund(8, 0)
        assert result == [0] * 8

    def test_single_pulse(self):
        """E(n,1) should produce exactly one hit at position 0."""
        result = self._bjorklund(8, 1)
        assert sum(result) == 1
        assert result[0] == 1

    def test_output_length_matches_steps(self):
        """Output pattern length must always equal step count."""
        for steps in range(1, 17):
            for pulses in range(0, steps + 1):
                result = self._bjorklund(steps, pulses)
                assert len(result) == steps, f"E({pulses},{steps}) length mismatch"

    def test_pulse_count_preserved(self):
        """Sum of hits must always equal the requested pulse count."""
        for steps in range(1, 17):
            for pulses in range(0, steps + 1):
                result = self._bjorklund(steps, pulses)
                assert sum(result) == pulses, f"E({pulses},{steps}) pulse count mismatch"


# ---------------------------------------------------------------------------
# Pure-logic: Scale intervals
# ---------------------------------------------------------------------------

class TestScaleIntervals:
    """Verify musical scale interval definitions are correct."""

    SCALES = {
        "major": [0, 2, 4, 5, 7, 9, 11],
        "minor": [0, 2, 3, 5, 7, 8, 10],
        "dorian": [0, 2, 3, 5, 7, 9, 10],
        "mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "pentatonic": [0, 2, 4, 7, 9],
        "blues": [0, 3, 5, 6, 7, 10],
        "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
        "chromatic": list(range(12)),
        "whole_tone": [0, 2, 4, 6, 8, 10],
    }

    def test_major_intervals(self):
        """Major scale should follow W-W-H-W-W-W pattern."""
        intervals = self.SCALES["major"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [2, 2, 1, 2, 2, 2]

    def test_minor_intervals(self):
        """Natural minor scale should follow W-H-W-W-H-W pattern."""
        intervals = self.SCALES["minor"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [2, 1, 2, 2, 1, 2]

    def test_dorian_intervals(self):
        """Dorian mode should follow W-H-W-W-W-H pattern."""
        intervals = self.SCALES["dorian"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [2, 1, 2, 2, 2, 1]

    def test_mixolydian_intervals(self):
        """Mixolydian mode should follow W-W-H-W-W-H pattern."""
        intervals = self.SCALES["mixolydian"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [2, 2, 1, 2, 2, 1]

    def test_pentatonic_has_5_notes(self):
        """Pentatonic scale must have exactly 5 notes."""
        assert len(self.SCALES["pentatonic"]) == 5

    def test_blues_has_6_notes(self):
        """Blues scale must have exactly 6 notes (pentatonic + blue note)."""
        assert len(self.SCALES["blues"]) == 6

    def test_chromatic_has_12_notes(self):
        """Chromatic scale must have all 12 semitones."""
        assert len(self.SCALES["chromatic"]) == 12
        assert self.SCALES["chromatic"] == list(range(12))

    def test_whole_tone_has_6_notes(self):
        """Whole-tone scale must have exactly 6 notes, all 2 semitones apart."""
        wt = self.SCALES["whole_tone"]
        assert len(wt) == 6
        steps = [wt[i + 1] - wt[i] for i in range(len(wt) - 1)]
        assert all(s == 2 for s in steps)

    def test_all_scales_start_at_zero(self):
        """Every scale must start at interval 0 (root)."""
        for name, intervals in self.SCALES.items():
            assert intervals[0] == 0, f"{name} scale does not start at 0"

    def test_all_intervals_within_octave(self):
        """All scale intervals must be in the range 0-11."""
        for name, intervals in self.SCALES.items():
            for interval in intervals:
                assert 0 <= interval <= 11, f"{name}: interval {interval} out of range"

    def test_all_scales_strictly_ascending(self):
        """Scale intervals must be in strictly ascending order."""
        for name, intervals in self.SCALES.items():
            for i in range(len(intervals) - 1):
                assert intervals[i] < intervals[i + 1], (
                    f"{name}: intervals not strictly ascending at position {i}"
                )


# ---------------------------------------------------------------------------
# Pure-logic: Chord voicings
# ---------------------------------------------------------------------------

class TestChordVoicings:
    """Test chord construction from interval tables."""

    CHORD_INTERVALS = {
        "major": [0, 4, 7],
        "minor": [0, 3, 7],
        "7th": [0, 4, 7, 10],
        "min7": [0, 3, 7, 10],
        "maj7": [0, 4, 7, 11],
        "dim": [0, 3, 6],
        "aug": [0, 4, 8],
        "sus4": [0, 5, 7],
        "sus2": [0, 2, 7],
    }

    def test_major_triad_c4(self):
        """C major triad from C4 should be C4, E4, G4."""
        root = 60  # C4
        chord = [root + i for i in self.CHORD_INTERVALS["major"]]
        assert chord == [60, 64, 67]

    def test_minor_triad_c4(self):
        """C minor triad from C4 should be C4, Eb4, G4."""
        root = 60
        chord = [root + i for i in self.CHORD_INTERVALS["minor"]]
        assert chord == [60, 63, 67]

    def test_dominant_seventh_c4(self):
        """C7 from C4 should be C4, E4, G4, Bb4."""
        root = 60
        chord = [root + i for i in self.CHORD_INTERVALS["7th"]]
        assert chord == [60, 64, 67, 70]

    def test_major_seventh_c4(self):
        """Cmaj7 from C4 should be C4, E4, G4, B4."""
        root = 60
        chord = [root + i for i in self.CHORD_INTERVALS["maj7"]]
        assert chord == [60, 64, 67, 71]

    def test_diminished_triad(self):
        """Diminished triad consists of two minor thirds."""
        intervals = self.CHORD_INTERVALS["dim"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [3, 3]

    def test_augmented_triad(self):
        """Augmented triad consists of two major thirds."""
        intervals = self.CHORD_INTERVALS["aug"]
        steps = [intervals[i + 1] - intervals[i] for i in range(len(intervals) - 1)]
        assert steps == [4, 4]

    def test_all_chords_start_at_root(self):
        """All chord interval lists must start at 0."""
        for name, intervals in self.CHORD_INTERVALS.items():
            assert intervals[0] == 0, f"{name} chord does not start at root"

    def test_all_intervals_positive(self):
        """All chord intervals must be positive and ascending."""
        for name, intervals in self.CHORD_INTERVALS.items():
            for i in range(1, len(intervals)):
                assert intervals[i] > intervals[i - 1], (
                    f"{name}: intervals not ascending at position {i}"
                )


# ---------------------------------------------------------------------------
# Pure-logic: Drum pattern definitions
# ---------------------------------------------------------------------------

class TestDrumPatternDefinitions:
    """Verify drum pattern data structures produce valid note data."""

    KICK, SNARE, HIHAT, OPEN_HAT = 36, 38, 42, 46
    RIDE, CRASH, CLAP, RIM = 51, 49, 39, 37

    PATTERNS = {
        "basic_rock": [
            (36, [0.0, 2.0], 1.0, 0.25),
            (38, [1.0, 3.0], 1.0, 0.25),
            (42, [i * 0.5 for i in range(8)], 0.7, 0.125),
        ],
        "house": [
            (36, [0.0, 1.0, 2.0, 3.0], 1.0, 0.25),
            (39, [1.0, 3.0], 0.9, 0.25),
            (46, [0.5, 1.5, 2.5, 3.5], 0.6, 0.25),
            (42, [i * 0.25 for i in range(16)], 0.5, 0.0625),
        ],
        "hiphop": [
            (36, [0.0, 0.75, 2.0, 2.5], 1.0, 0.25),
            (38, [1.0, 3.0], 1.0, 0.25),
            (42, [i * 0.5 for i in range(8)], 0.65, 0.125),
        ],
        "trap": [
            (36, [0.0, 0.75, 2.0], 1.0, 0.25),
            (38, [1.0, 3.0], 1.0, 0.25),
            (42, [i * 0.125 for i in range(32)], 0.55, 0.0625),
            (46, [1.75, 3.75], 0.7, 0.125),
        ],
    }

    def test_basic_rock_has_kick_snare_hihat(self):
        """Basic rock pattern must contain kick, snare, and hihat layers."""
        pitches = {layer[0] for layer in self.PATTERNS["basic_rock"]}
        assert self.KICK in pitches
        assert self.SNARE in pitches
        assert self.HIHAT in pitches

    def test_house_four_on_floor(self):
        """House pattern must have kick on every beat (4-on-the-floor)."""
        kick_layer = [layer for layer in self.PATTERNS["house"] if layer[0] == self.KICK][0]
        assert kick_layer[1] == [0.0, 1.0, 2.0, 3.0]

    def test_all_positions_within_4_beats(self):
        """All note positions in default 4-beat patterns must be < 4.0."""
        for style, layers in self.PATTERNS.items():
            for pitch, positions, vel_ratio, duration in layers:
                for pos in positions:
                    assert 0.0 <= pos < 4.0, (
                        f"{style}: position {pos} for pitch {pitch} is out of range"
                    )

    def test_all_velocity_ratios_valid(self):
        """Velocity ratios must be between 0 and 1 (exclusive of 0)."""
        for style, layers in self.PATTERNS.items():
            for pitch, positions, vel_ratio, duration in layers:
                assert 0.0 < vel_ratio <= 1.0, (
                    f"{style}: vel_ratio {vel_ratio} for pitch {pitch} is invalid"
                )

    def test_all_durations_positive(self):
        """All note durations must be positive."""
        for style, layers in self.PATTERNS.items():
            for pitch, positions, vel_ratio, duration in layers:
                assert duration > 0, (
                    f"{style}: duration {duration} for pitch {pitch} is not positive"
                )

    def test_all_pitches_valid_midi(self):
        """All pitches must be valid MIDI note numbers (0-127)."""
        for style, layers in self.PATTERNS.items():
            for pitch, positions, vel_ratio, duration in layers:
                assert 0 <= pitch <= 127, (
                    f"{style}: pitch {pitch} is not a valid MIDI note"
                )

    def test_pattern_note_generation(self):
        """Simulate note generation from pattern data and verify output shape."""
        velocity = 100
        clip_length = 4.0
        for style, layers in self.PATTERNS.items():
            notes = []
            for pitch, positions, vel_ratio, duration in layers:
                for pos in positions:
                    if pos >= clip_length:
                        continue
                    notes.append({
                        "pitch": pitch,
                        "start_time": pos,
                        "duration": duration,
                        "velocity": max(1, min(127, int(velocity * vel_ratio))),
                    })
            assert len(notes) > 0, f"{style} produced no notes"
            for note in notes:
                assert 0 <= note["pitch"] <= 127
                assert 1 <= note["velocity"] <= 127
                assert note["duration"] > 0
                assert note["start_time"] >= 0


# ---------------------------------------------------------------------------
# Integration: tools registered on a FastMCP instance with mocked connection
# ---------------------------------------------------------------------------

def _setup_creative_tools(mock_conn):
    """Create a FastMCP instance, register creative tools, and patch the
    module-level get_ableton_connection so tool closures use our mock.

    Returns (mcp, patch_context) -- caller must enter/exit the context.
    """
    from mcp.server.fastmcp import FastMCP
    from MCP_Server.tools.creative import register_tools
    mcp = FastMCP("test")
    register_tools(mcp)
    return mcp


def _get_add_notes_calls(mock_conn):
    """Extract add_notes_to_clip calls from the mock."""
    return [c for c in mock_conn.send_command.call_args_list
            if c[0][0] == "add_notes_to_clip"]


class TestCreativeToolsIntegration:
    """Test creative tools through the _tool_handler async wrapper.

    Each test patches ``MCP_Server.tools.creative.get_ableton_connection``
    (the module-level name bound by ``from ... import``) so the tool
    closures use the per-test mock rather than the original function.
    """

    @pytest.mark.asyncio
    async def test_euclidean_rhythm_tool(self, patch_ableton):
        """generate_euclidean_rhythm tool should write correct number of notes."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_euclidean_rhythm")
            assert tool_fn is not None, "generate_euclidean_rhythm tool not registered"

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      steps=8, pulses=3, pitch=36, velocity=100)
            assert "3 hits" in result or "3" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            assert len(add_calls) == 1
            notes = add_calls[0][0][1]["notes"]
            assert len(notes) == 3
            for note in notes:
                assert note["pitch"] == 36
                assert note["velocity"] == 100

    @pytest.mark.asyncio
    async def test_generate_drum_pattern_basic_rock(self, patch_ableton):
        """generate_drum_pattern with basic_rock should produce kick+snare+hihat."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_drum_pattern")
            assert tool_fn is not None

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      style="basic_rock", clip_length=4.0, velocity=100)
            assert "basic_rock" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            assert len(add_calls) == 1
            notes = add_calls[0][0][1]["notes"]
            pitches = {n["pitch"] for n in notes}
            assert 36 in pitches  # kick
            assert 38 in pitches  # snare
            assert 42 in pitches  # hihat

    @pytest.mark.asyncio
    async def test_generate_drum_pattern_invalid_style(self, patch_ableton):
        """Invalid drum pattern style should return an Invalid input message."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_drum_pattern")
            ctx = MagicMock()
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      style="nonexistent")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_generate_drum_pattern_all_styles(self, patch_ableton):
        """Every drum style should produce valid notes without error."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)

            styles = ["basic_rock", "house", "hiphop", "dnb", "halftime",
                      "jazz_ride", "latin", "trap"]

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_drum_pattern")
            ctx = MagicMock()

            for style in styles:
                patch_ableton.send_command.reset_mock()
                patch_ableton.send_command.return_value = {"status": "success"}

                result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                          style=style)
                assert "Error" not in result, f"Style {style} returned error: {result}"

                add_calls = _get_add_notes_calls(patch_ableton)
                assert len(add_calls) == 1, f"Style {style} did not call add_notes_to_clip"
                notes = add_calls[0][0][1]["notes"]
                assert len(notes) > 0, f"Style {style} produced no notes"

    @pytest.mark.asyncio
    async def test_scale_constrained_generate_ascending(self, patch_ableton):
        """scale_constrained_generate with ascending algorithm should produce ordered pitches."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("scale_constrained_generate")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      scale_name="major", root=60, note_count=7,
                                      algorithm="ascending", octave_range=1)
            assert "7 scale-constrained notes" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            notes = add_calls[0][0][1]["notes"]
            assert len(notes) == 7
            # Ascending pattern pitches should follow major scale
            pitches = [n["pitch"] for n in notes]
            expected_scale = [60, 62, 64, 65, 67, 69, 71]  # C major from C4
            assert pitches == expected_scale

    @pytest.mark.asyncio
    async def test_scale_constrained_invalid_scale(self, patch_ableton):
        """Unknown scale name should return Invalid input error."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("scale_constrained_generate")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      scale_name="doesnotexist")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_generate_arpeggio_up(self, patch_ableton):
        """Arpeggio with 'up' pattern should cycle through chord tones ascending."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_arpeggio")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      root=60, chord_type="major", pattern="up",
                                      octaves=1, note_length=0.25, clip_length=1.5)
            assert "up arpeggio" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            notes = add_calls[0][0][1]["notes"]
            # 1.5 beats / 0.25 = 6 steps
            assert len(notes) == 6
            # First 3 notes should be C, E, G (1 octave major)
            first_three = [n["pitch"] for n in notes[:3]]
            assert first_three == [60, 64, 67]

    @pytest.mark.asyncio
    async def test_generate_arpeggio_invalid_chord_type(self, patch_ableton):
        """Unknown chord type should return Invalid input error."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_arpeggio")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      chord_type="quartal")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_stutter_effect_velocity_decay(self, patch_ableton):
        """Stutter effect with velocity_decay < 1 should produce decreasing velocities."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("stutter_effect")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      stutter_count=5, velocity=100,
                                      velocity_decay=0.8, pitch=60)
            assert "5 hits" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            notes = add_calls[0][0][1]["notes"]
            velocities = [n["velocity"] for n in notes]
            # Each velocity should be <= the previous one
            for i in range(1, len(velocities)):
                assert velocities[i] <= velocities[i - 1], (
                    f"Velocity did not decay at position {i}: {velocities}"
                )

    @pytest.mark.asyncio
    async def test_transform_notes_transpose(self, patch_ableton):
        """transform_notes with 'transpose' should shift pitches by the given amount."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)

            # Mock get_clip_notes to return known notes
            def cmd_handler(cmd, params=None):
                if cmd == "get_clip_notes":
                    return {
                        "notes": [
                            {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
                            {"pitch": 64, "start_time": 1.0, "duration": 1.0, "velocity": 100},
                        ]
                    }
                return {"status": "success"}
            patch_ableton.send_command.side_effect = cmd_handler

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("transform_notes")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      operation="transpose", amount=7)
            assert "transpose" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            assert len(add_calls) == 1
            notes = add_calls[0][0][1]["notes"]
            assert notes[0]["pitch"] == 67  # 60 + 7
            assert notes[1]["pitch"] == 71  # 64 + 7

    @pytest.mark.asyncio
    async def test_transform_notes_invalid_operation(self, patch_ableton):
        """Invalid transform operation should return Invalid input error."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("transform_notes")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      operation="shuffle")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_generate_chord_progression(self, patch_ableton):
        """generate_chord_progression with I,V,vi,IV should produce 4 chords."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_chord_progression")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      root=60, scale_name="major",
                                      progression="I,V,vi,IV",
                                      note_length=4.0, velocity=90)
            assert "4-chord progression" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            notes = add_calls[0][0][1]["notes"]
            # 4 chords x 3 notes each (triads) = 12 notes
            assert len(notes) == 12

    @pytest.mark.asyncio
    async def test_generate_bass_line_root_fifth(self, patch_ableton):
        """Bass line with root_fifth pattern should alternate root and fifth."""
        with patch('MCP_Server.tools.creative.get_ableton_connection',
                    return_value=patch_ableton):
            mcp = _setup_creative_tools(patch_ableton)
            patch_ableton.send_command.return_value = {"status": "success"}

            tools = mcp._tool_manager._tools
            tool_fn = tools.get("generate_bass_line")
            ctx = MagicMock()

            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      root=36, pattern_type="root_fifth",
                                      note_length=0.5, clip_length=2.0)
            assert "root_fifth" in result

            add_calls = _get_add_notes_calls(patch_ableton)
            notes = add_calls[0][0][1]["notes"]
            # 2.0 / 0.5 = 4 steps
            assert len(notes) == 4
            # Alternates root (36) and fifth (36+7=43)
            pitches = [n["pitch"] for n in notes]
            assert pitches == [36, 43, 36, 43]
