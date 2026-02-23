"""Creative / generative MIDI tool handlers for AbletonBridge."""
import json
import math
from typing import List, Dict, Any
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_range, _validate_notes


def register_tools(mcp):

    @mcp.tool()
    @_tool_handler("generating euclidean rhythm")
    def generate_euclidean_rhythm(ctx: Context, track_index: int, clip_index: int,
                                    steps: int, pulses: int, pitch: int = 36,
                                    velocity: int = 100, rotation: int = 0,
                                    note_length: float = 0.25,
                                    clip_length: float = None) -> str:
        """Generate a Euclidean rhythm pattern and write it to a MIDI clip.

        Euclidean rhythms distribute N pulses as evenly as possible across K steps.
        Common patterns: (8,3)=tresillo, (8,5)=cinquillo, (16,9)=rumba.

        Parameters:
        - track_index: The index of the MIDI track
        - clip_index: The index of the clip slot (clip must exist)
        - steps: Total number of steps in the pattern (e.g. 8, 16)
        - pulses: Number of active hits (must be <= steps)
        - pitch: MIDI note number for the hits (default: 36 = kick)
        - velocity: Velocity of the hits (1-127, default: 100)
        - rotation: Rotate the pattern by N steps (default: 0)
        - note_length: Duration of each note in beats (default: 0.25)
        - clip_length: Total clip length in beats (default: steps * note_length * steps/steps)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if not isinstance(steps, int) or steps < 1:
            raise ValueError("steps must be a positive integer")
        if not isinstance(pulses, int) or pulses < 0 or pulses > steps:
            raise ValueError("pulses must be between 0 and steps")
        _validate_range(pitch, "pitch", 0, 127)
        _validate_range(velocity, "velocity", 1, 127)

        # Bjorklund's algorithm
        def bjorklund(steps, pulses):
            if pulses == 0:
                return [0] * steps
            if pulses >= steps:
                return [1] * steps
            pattern = [[1] for _ in range(pulses)] + [[0] for _ in range(steps - pulses)]
            while True:
                remainder = len(pattern) - pulses
                if remainder <= 1:
                    break
                new_pattern = []
                i = 0
                j = len(pattern) - 1
                count = 0
                while i < j and count < pulses:
                    new_pattern.append(pattern[i] + pattern[j])
                    i += 1
                    j -= 1
                    count += 1
                while i <= j:
                    new_pattern.append(pattern[i])
                    i += 1
                pattern = new_pattern
                pulses = count
            result = []
            for group in pattern:
                result.extend(group)
            return result

        pattern = bjorklund(steps, pulses)

        # Apply rotation
        if rotation != 0:
            rotation = rotation % len(pattern)
            pattern = pattern[rotation:] + pattern[:rotation]

        # Calculate step duration
        step_duration = note_length if note_length else 0.25
        if clip_length is None:
            clip_length = steps * step_duration

        # Build notes
        notes = []
        for i, hit in enumerate(pattern):
            if hit:
                notes.append({
                    "pitch": int(pitch),
                    "start_time": i * step_duration,
                    "duration": note_length,
                    "velocity": int(velocity),
                })

        if not notes:
            return "No notes generated (0 pulses)"

        # Write to clip
        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated Euclidean rhythm ({steps},{pulses}) with {len(notes)} hits on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("humanizing notes")
    def humanize_notes(ctx: Context, track_index: int, clip_index: int,
                         timing_amount: float = 0.02, velocity_amount: float = 10.0,
                         pitch_range: int = 0) -> str:
        """Add humanization (timing/velocity randomization) to notes in a MIDI clip.

        Reads existing notes, applies random variation, and writes them back.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - timing_amount: Max random timing offset in beats (default: 0.02, ~30ms at 120bpm)
        - velocity_amount: Max random velocity variation (default: 10.0)
        - pitch_range: Max random pitch offset in semitones (default: 0, no pitch change)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        import random

        ableton = get_ableton_connection()

        # Get existing notes
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "start_time": 0.0,
            "time_span": 0.0,
            "start_pitch": 0,
            "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found in clip to humanize"

        # Remove existing notes
        ableton.send_command("remove_notes_range", {
            "track_index": track_index,
            "clip_index": clip_index,
            "from_time": 0.0,
            "time_span": 999999.0,
            "from_pitch": 0,
            "pitch_span": 128,
        })

        # Apply humanization
        humanized = []
        for note in notes:
            new_note = dict(note)
            if timing_amount > 0:
                new_note["start_time"] = max(0, note["start_time"] + random.uniform(-timing_amount, timing_amount))
            if velocity_amount > 0:
                new_vel = note["velocity"] + random.uniform(-velocity_amount, velocity_amount)
                new_note["velocity"] = max(1, min(127, int(new_vel)))
            if pitch_range > 0:
                new_pitch = note["pitch"] + random.randint(-pitch_range, pitch_range)
                new_note["pitch"] = max(0, min(127, new_pitch))
            humanized.append(new_note)

        # Write back
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": humanized,
        })

        return f"Humanized {len(humanized)} notes (timing\u00b1{timing_amount}, velocity\u00b1{velocity_amount})"


    @mcp.tool()
    @_tool_handler("generating scale-constrained notes")
    def scale_constrained_generate(ctx: Context, track_index: int, clip_index: int,
                                      scale_name: str = "major", root: int = 60,
                                      note_count: int = 16, octave_range: int = 2,
                                      note_length: float = 0.25,
                                      velocity_min: int = 60, velocity_max: int = 120,
                                      algorithm: str = "random") -> str:
        """Generate notes constrained to a musical scale and write to a MIDI clip.

        Parameters:
        - track_index: The index of the MIDI track
        - clip_index: The index of the clip slot (clip must exist)
        - scale_name: Scale type: "major", "minor", "dorian", "mixolydian", "pentatonic", "blues", "harmonic_minor", "melodic_minor", "chromatic", "whole_tone"
        - root: Root MIDI note (default: 60 = C4)
        - note_count: Number of notes to generate (default: 16)
        - octave_range: Range of octaves above root (default: 2)
        - note_length: Duration per note in beats (default: 0.25)
        - velocity_min: Minimum velocity (default: 60)
        - velocity_max: Maximum velocity (default: 120)
        - algorithm: "random" (default), "ascending", "descending", "pendulum"
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        import random

        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "dorian": [0, 2, 3, 5, 7, 9, 10],
            "mixolydian": [0, 2, 4, 5, 7, 9, 10],
            "pentatonic": [0, 2, 4, 7, 9],
            "blues": [0, 3, 5, 6, 7, 10],
            "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
            "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
            "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "whole_tone": [0, 2, 4, 6, 8, 10],
        }

        if scale_name not in scales:
            raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(scales.keys())}")

        # Build all pitches in range
        intervals = scales[scale_name]
        pitches = []
        root_base = root
        for octave in range(octave_range + 1):
            for interval in intervals:
                p = root_base + octave * 12 + interval
                if 0 <= p <= 127:
                    pitches.append(p)

        if not pitches:
            raise ValueError("No valid pitches in the specified range")

        # Generate sequence based on algorithm
        if algorithm == "ascending":
            sequence = [pitches[i % len(pitches)] for i in range(note_count)]
        elif algorithm == "descending":
            rev = list(reversed(pitches))
            sequence = [rev[i % len(rev)] for i in range(note_count)]
        elif algorithm == "pendulum":
            cycle = pitches + list(reversed(pitches[1:-1])) if len(pitches) > 2 else pitches
            sequence = [cycle[i % len(cycle)] for i in range(note_count)]
        else:  # random
            sequence = [random.choice(pitches) for _ in range(note_count)]

        notes = []
        for i, pitch in enumerate(sequence):
            notes.append({
                "pitch": pitch,
                "start_time": i * note_length,
                "duration": note_length,
                "velocity": random.randint(velocity_min, velocity_max),
            })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {note_count} scale-constrained notes ({scale_name} from {root}) on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("transforming notes")
    def transform_notes(ctx: Context, track_index: int, clip_index: int,
                          operation: str, amount: int = 0) -> str:
        """Transform existing notes in a MIDI clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - operation: "transpose" (shift pitch by amount semitones), "reverse" (reverse note order in time),
                     "invert" (invert pitches around center), "double_speed" (halve durations),
                     "half_speed" (double durations), "legato" (extend notes to fill gaps)
        - amount: Amount for transpose operation (semitones, positive=up, negative=down)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if operation not in ("transpose", "reverse", "invert", "double_speed", "half_speed", "legato"):
            raise ValueError("operation must be one of: transpose, reverse, invert, double_speed, half_speed, legato")

        ableton = get_ableton_connection()
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": track_index, "clip_index": clip_index,
            "start_time": 0.0, "time_span": 0.0,
            "start_pitch": 0, "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found to transform"

        # Remove old notes
        ableton.send_command("remove_notes_range", {
            "track_index": track_index, "clip_index": clip_index,
            "from_time": 0.0, "time_span": 999999.0,
            "from_pitch": 0, "pitch_span": 128,
        })

        if operation == "transpose":
            for n in notes:
                n["pitch"] = max(0, min(127, n["pitch"] + amount))

        elif operation == "reverse":
            if notes:
                max_end = max(n["start_time"] + n["duration"] for n in notes)
                for n in notes:
                    n["start_time"] = max_end - n["start_time"] - n["duration"]

        elif operation == "invert":
            pitches = [n["pitch"] for n in notes]
            center = (min(pitches) + max(pitches)) / 2.0
            for n in notes:
                n["pitch"] = max(0, min(127, int(2 * center - n["pitch"])))

        elif operation == "double_speed":
            for n in notes:
                n["start_time"] /= 2.0
                n["duration"] /= 2.0

        elif operation == "half_speed":
            for n in notes:
                n["start_time"] *= 2.0
                n["duration"] *= 2.0

        elif operation == "legato":
            sorted_notes = sorted(notes, key=lambda n: (n["pitch"], n["start_time"]))
            i = 0
            while i < len(sorted_notes) - 1:
                curr = sorted_notes[i]
                nxt = sorted_notes[i + 1]
                if curr["pitch"] == nxt["pitch"]:
                    gap = nxt["start_time"] - (curr["start_time"] + curr["duration"])
                    if gap > 0:
                        curr["duration"] += gap
                i += 1

        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Transformed {len(notes)} notes with '{operation}' on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("copying notes between clips")
    def copy_notes_between_clips(ctx: Context, src_track: int, src_clip: int,
                                    dest_track: int, dest_clip: int,
                                    transpose: int = 0, time_offset: float = 0.0) -> str:
        """Copy all notes from one MIDI clip to another, with optional transpose and time offset.

        Parameters:
        - src_track: Source track index
        - src_clip: Source clip slot index
        - dest_track: Destination track index
        - dest_clip: Destination clip slot index
        - transpose: Semitones to transpose copied notes (default: 0)
        - time_offset: Beat offset to shift copied notes in time (default: 0.0)
        """
        _validate_index(src_track, "src_track")
        _validate_index(src_clip, "src_clip")
        _validate_index(dest_track, "dest_track")
        _validate_index(dest_clip, "dest_clip")

        ableton = get_ableton_connection()
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": src_track, "clip_index": src_clip,
            "start_time": 0.0, "time_span": 0.0,
            "start_pitch": 0, "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found in source clip"

        copied = []
        for n in notes:
            new_note = dict(n)
            new_note["pitch"] = max(0, min(127, n["pitch"] + transpose))
            new_note["start_time"] = max(0, n["start_time"] + time_offset)
            copied.append(new_note)

        ableton.send_command("add_notes_to_clip", {
            "track_index": dest_track,
            "clip_index": dest_clip,
            "notes": copied,
        })

        return f"Copied {len(copied)} notes from track {src_track} clip {src_clip} to track {dest_track} clip {dest_clip}"


    @mcp.tool()
    @_tool_handler("batch setting follow actions")
    def batch_set_follow_actions(ctx: Context, track_index: int,
                                   clip_indices: str,
                                   follow_action_0: int = 4,
                                   follow_action_1: int = 0,
                                   follow_action_probability: float = 1.0,
                                   follow_action_time: float = None,
                                   follow_action_enabled: bool = True,
                                   follow_action_linked: bool = True) -> str:
        """Set follow actions on multiple clips at once.

        Parameters:
        - track_index: The track containing the clips
        - clip_indices: Comma-separated clip slot indices, e.g. "0,1,2,3"
        - follow_action_0: First action (default: 4=Next)
        - follow_action_1: Second action (default: 0=None)
        - follow_action_probability: Probability (0.0-1.0, default: 1.0)
        - follow_action_time: Time in beats (default: None = use clip length)
        - follow_action_enabled: Enable follow actions (default: True)
        - follow_action_linked: Link to clip end (default: True)
        """
        _validate_index(track_index, "track_index")

        indices = [int(i.strip()) for i in clip_indices.split(",") if i.strip()]
        if not indices:
            raise ValueError("No valid clip indices provided")

        ableton = get_ableton_connection()
        results = []
        for ci in indices:
            params = {
                "track_index": track_index,
                "clip_index": ci,
                "follow_action_0": follow_action_0,
                "follow_action_1": follow_action_1,
                "follow_action_probability": follow_action_probability,
                "follow_action_enabled": follow_action_enabled,
                "follow_action_linked": follow_action_linked,
            }
            if follow_action_time is not None:
                params["follow_action_time"] = follow_action_time
            try:
                ableton.send_command("set_clip_follow_actions", params)
                results.append(f"clip {ci}: ok")
            except Exception as e:
                results.append(f"clip {ci}: {e}")

        return f"Batch follow actions on track {track_index}: {'; '.join(results)}"


    @mcp.tool()
    @_tool_handler("randomizing clip notes")
    def randomize_clip_notes(ctx: Context, track_index: int, clip_index: int,
                               pitch_min: int = 36, pitch_max: int = 84,
                               note_count: int = 16, note_length: float = 0.25,
                               velocity_min: int = 60, velocity_max: int = 120,
                               clip_length: float = 4.0, density: float = 1.0) -> str:
        """Generate random notes with constraints and write to a MIDI clip.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - pitch_min: Lowest MIDI pitch (default: 36)
        - pitch_max: Highest MIDI pitch (default: 84)
        - note_count: Number of notes to generate (default: 16)
        - note_length: Duration of each note (default: 0.25 beats)
        - velocity_min: Minimum velocity (default: 60)
        - velocity_max: Maximum velocity (default: 120)
        - clip_length: Total length to distribute notes across (default: 4.0 beats)
        - density: Probability each grid slot has a note (0.0-1.0, default: 1.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(density, "density", 0.0, 1.0)
        import random

        notes = []
        grid_slots = int(clip_length / note_length) if note_length > 0 else note_count
        for i in range(min(note_count, grid_slots)):
            if random.random() > density:
                continue
            notes.append({
                "pitch": random.randint(int(pitch_min), int(pitch_max)),
                "start_time": i * note_length,
                "duration": note_length,
                "velocity": random.randint(int(velocity_min), int(velocity_max)),
            })

        if not notes:
            return "No notes generated (density too low or count is 0)"

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {len(notes)} random notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("creating polyrhythm")
    def create_polyrhythm(ctx: Context, track_index: int, clip_index: int,
                            rhythms: str, pitches: str = "36,38,42",
                            clip_length: float = 4.0, velocity: int = 100) -> str:
        """Create polyrhythmic patterns by layering multiple rhythmic divisions.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - rhythms: Comma-separated number of divisions per bar, e.g. "3,4,5" creates 3-against-4-against-5
        - pitches: Comma-separated MIDI pitches for each rhythm layer (default: "36,38,42")
        - clip_length: Total clip length in beats (default: 4.0)
        - velocity: Base velocity (default: 100)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)

        rhythm_list = [int(r.strip()) for r in rhythms.split(",") if r.strip()]
        pitch_list = [int(p.strip()) for p in pitches.split(",") if p.strip()]

        if not rhythm_list:
            raise ValueError("No valid rhythms provided")

        notes = []
        for layer, divisions in enumerate(rhythm_list):
            pitch = pitch_list[layer % len(pitch_list)] if pitch_list else 60 + layer * 5
            step = clip_length / divisions
            for i in range(divisions):
                notes.append({
                    "pitch": pitch,
                    "start_time": i * step,
                    "duration": step * 0.5,
                    "velocity": int(velocity),
                })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Created polyrhythm ({rhythms}) with {len(notes)} notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("creating stutter effect")
    def stutter_effect(ctx: Context, track_index: int, clip_index: int,
                         stutter_rate: float = 0.125, stutter_count: int = 8,
                         pitch: int = 60, velocity: int = 100,
                         velocity_decay: float = 0.95) -> str:
        """Create a stutter/glitch pattern by writing rapid repeated notes.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - stutter_rate: Time between stutters in beats (default: 0.125 = 32nd note)
        - stutter_count: Number of stutter repetitions (default: 8)
        - pitch: MIDI note to repeat (default: 60)
        - velocity: Starting velocity (default: 100)
        - velocity_decay: Velocity multiplier per repetition (default: 0.95)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)
        _validate_range(velocity_decay, "velocity_decay", 0.0, 1.5)

        notes = []
        current_velocity = float(velocity)
        for i in range(stutter_count):
            notes.append({
                "pitch": int(pitch),
                "start_time": i * stutter_rate,
                "duration": stutter_rate * 0.8,
                "velocity": max(1, min(127, int(current_velocity))),
            })
            current_velocity *= velocity_decay

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Created stutter effect ({stutter_count} hits at {stutter_rate} beat intervals) on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("duplicating with variation")
    def duplicate_with_variation(ctx: Context, src_track: int, src_clip: int,
                                   dest_track: int, dest_clip: int,
                                   timing_variation: float = 0.02,
                                   velocity_variation: float = 10.0,
                                   pitch_variation: int = 0,
                                   transpose: int = 0) -> str:
        """Duplicate a clip's notes to another clip with random humanization applied.

        Combines copy + humanize in one step.

        Parameters:
        - src_track: Source track index
        - src_clip: Source clip index
        - dest_track: Destination track index
        - dest_clip: Destination clip index (clip must exist)
        - timing_variation: Max timing offset in beats (default: 0.02)
        - velocity_variation: Max velocity variation (default: 10.0)
        - pitch_variation: Max pitch offset in semitones (default: 0)
        - transpose: Fixed transpose in semitones (default: 0)
        """
        _validate_index(src_track, "src_track")
        _validate_index(src_clip, "src_clip")
        _validate_index(dest_track, "dest_track")
        _validate_index(dest_clip, "dest_clip")
        import random

        ableton = get_ableton_connection()
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": src_track, "clip_index": src_clip,
            "start_time": 0.0, "time_span": 0.0,
            "start_pitch": 0, "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found in source clip"

        varied = []
        for n in notes:
            new_note = dict(n)
            new_note["pitch"] = max(0, min(127, n["pitch"] + transpose + random.randint(-pitch_variation, pitch_variation)))
            new_note["start_time"] = max(0, n["start_time"] + random.uniform(-timing_variation, timing_variation))
            new_vel = n["velocity"] + random.uniform(-velocity_variation, velocity_variation)
            new_note["velocity"] = max(1, min(127, int(new_vel)))
            varied.append(new_note)

        ableton.send_command("add_notes_to_clip", {
            "track_index": dest_track,
            "clip_index": dest_clip,
            "notes": varied,
        })

        return f"Duplicated {len(varied)} notes from track {src_track} clip {src_clip} to track {dest_track} clip {dest_clip} with variation"


    @mcp.tool()
    @_tool_handler("generating chord progression")
    def generate_chord_progression(ctx: Context, track_index: int, clip_index: int,
                                      root: int = 60, scale_name: str = "major",
                                      progression: str = "I,V,vi,IV",
                                      note_length: float = 4.0,
                                      velocity: int = 90, voicing: str = "close") -> str:
        """Generate a chord progression and write it to a MIDI clip.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - root: Root MIDI note (default: 60 = C4)
        - scale_name: Scale type: "major", "minor", "dorian", "mixolydian", "harmonic_minor"
        - progression: Comma-separated Roman numeral chord symbols, e.g. "I,V,vi,IV"
          Supported: I, ii, iii, IV, V, vi, vii (major scale degrees)
          Uppercase = major triad, lowercase = minor triad
          Suffix "7" for seventh chords (e.g. "V7", "ii7")
        - note_length: Duration per chord in beats (default: 4.0 = one bar)
        - velocity: Note velocity (default: 90)
        - voicing: "close" (root position, default), "spread" (notes across octaves), "drop2" (drop-2 voicing)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)

        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "dorian": [0, 2, 3, 5, 7, 9, 10],
            "mixolydian": [0, 2, 4, 5, 7, 9, 10],
            "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        }
        if scale_name not in scales:
            raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(scales.keys())}")

        intervals = scales[scale_name]

        # Map Roman numerals to scale degrees (0-indexed)
        numeral_map = {
            "I": 0, "i": 0, "II": 1, "ii": 1, "III": 2, "iii": 2,
            "IV": 3, "iv": 3, "V": 4, "v": 4, "VI": 5, "vi": 5,
            "VII": 6, "vii": 6,
        }

        def build_chord(degree_str):
            has_seventh = degree_str.endswith("7")
            numeral = degree_str.rstrip("7")
            degree = numeral_map.get(numeral)
            if degree is None:
                raise ValueError(f"Unknown chord numeral '{degree_str}'")
            is_minor = numeral[0].islower()

            # Get scale tone for this degree
            root_interval = intervals[degree % len(intervals)]

            # Build chord intervals (major or minor triad)
            if is_minor:
                chord_intervals = [0, 3, 7]
                if has_seventh:
                    chord_intervals.append(10)  # minor 7th
            else:
                chord_intervals = [0, 4, 7]
                if has_seventh:
                    chord_intervals.append(11 if degree == 4 else 10)  # dominant 7th for V, minor 7th otherwise

            return [root_interval + ci for ci in chord_intervals]

        chord_symbols = [c.strip() for c in progression.split(",") if c.strip()]
        notes = []
        for i, symbol in enumerate(chord_symbols):
            chord_intervals = build_chord(symbol)
            start_time = i * note_length

            for j, interval in enumerate(chord_intervals):
                pitch = root + interval
                if voicing == "spread" and j > 0:
                    pitch += (j % 2) * 12  # alternate octaves
                elif voicing == "drop2" and j == 1 and len(chord_intervals) >= 3:
                    pitch -= 12  # drop second voice down an octave

                pitch = max(0, min(127, pitch))
                notes.append({
                    "pitch": pitch,
                    "start_time": start_time,
                    "duration": note_length,
                    "velocity": int(velocity),
                })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {len(chord_symbols)}-chord progression ({progression}) with {len(notes)} notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("generating arpeggio")
    def generate_arpeggio(ctx: Context, track_index: int, clip_index: int,
                             root: int = 60, chord_type: str = "major",
                             pattern: str = "up", octaves: int = 2,
                             note_length: float = 0.25, clip_length: float = 4.0,
                             velocity: int = 100, gate: float = 0.8) -> str:
        """Generate an arpeggio pattern and write it to a MIDI clip.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - root: Root MIDI note (default: 60 = C4)
        - chord_type: "major", "minor", "7th", "min7", "maj7", "dim", "aug", "sus4", "sus2"
        - pattern: "up", "down", "up_down", "down_up", "random", "played" (as defined order)
        - octaves: How many octaves to span (default: 2)
        - note_length: Duration per note in beats (default: 0.25 = 16th note)
        - clip_length: Total clip length in beats (default: 4.0)
        - velocity: Base velocity (default: 100)
        - gate: Note gate as fraction of note_length (default: 0.8)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)
        _validate_range(gate, "gate", 0.1, 1.0)

        chord_intervals = {
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
        if chord_type not in chord_intervals:
            raise ValueError(f"Unknown chord_type '{chord_type}'. Available: {', '.join(chord_intervals.keys())}")

        # Build pitches across octaves
        base_intervals = chord_intervals[chord_type]
        pitches = []
        for oct in range(octaves):
            for interval in base_intervals:
                p = root + oct * 12 + interval
                if 0 <= p <= 127:
                    pitches.append(p)

        if not pitches:
            raise ValueError("No valid pitches in range")

        import random

        # Apply pattern
        if pattern == "up":
            sequence = pitches
        elif pattern == "down":
            sequence = list(reversed(pitches))
        elif pattern == "up_down":
            sequence = pitches + list(reversed(pitches[1:-1])) if len(pitches) > 2 else pitches
        elif pattern == "down_up":
            rev = list(reversed(pitches))
            sequence = rev + pitches[1:-1] if len(pitches) > 2 else rev
        elif pattern == "random":
            sequence = pitches[:]
            random.shuffle(sequence)
        else:  # "played" or unknown
            sequence = pitches

        # Fill clip_length by repeating sequence
        notes = []
        total_steps = int(clip_length / note_length)
        for i in range(total_steps):
            pitch = sequence[i % len(sequence)]
            notes.append({
                "pitch": pitch,
                "start_time": i * note_length,
                "duration": note_length * gate,
                "velocity": int(velocity),
            })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {pattern} arpeggio ({chord_type}, {octaves} octaves) with {len(notes)} notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("generating drum pattern")
    def generate_drum_pattern(ctx: Context, track_index: int, clip_index: int,
                                 style: str = "basic_rock",
                                 clip_length: float = 4.0,
                                 velocity: int = 100,
                                 swing: float = 0.0) -> str:
        """Generate a drum pattern and write it to a MIDI clip on a Drum Rack track.

        Uses General MIDI drum mapping (kick=36, snare=38, hihat=42, open_hat=46,
        ride=51, crash=49, tom_low=45, tom_mid=47, tom_hi=50, clap=39, rim=37).

        Parameters:
        - track_index: The MIDI track index (should have a Drum Rack)
        - clip_index: The clip slot index (clip must exist)
        - style: Pattern style:
            "basic_rock" -- standard 4/4 rock beat
            "house" -- four-on-the-floor house
            "hiphop" -- boom bap hip-hop
            "dnb" -- drum and bass breakbeat
            "halftime" -- half-time groove
            "jazz_ride" -- jazz ride pattern
            "latin" -- Latin percussion pattern
            "trap" -- trap hi-hat pattern
        - clip_length: Total clip length in beats (default: 4.0)
        - velocity: Base velocity (default: 100)
        - swing: Swing amount 0.0-1.0, shifts offbeat notes late (default: 0.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)
        _validate_range(swing, "swing", 0.0, 1.0)

        KICK, SNARE, HIHAT, OPEN_HAT = 36, 38, 42, 46
        RIDE, CRASH, CLAP, RIM = 51, 49, 39, 37
        TOM_LO, TOM_MID, TOM_HI = 45, 47, 50

        # Define patterns as (pitch, [beat positions], velocity_ratio, duration)
        patterns = {
            "basic_rock": [
                (KICK,    [0.0, 2.0],           1.0, 0.25),
                (SNARE,   [1.0, 3.0],           1.0, 0.25),
                (HIHAT,   [i * 0.5 for i in range(8)], 0.7, 0.125),
            ],
            "house": [
                (KICK,    [0.0, 1.0, 2.0, 3.0], 1.0, 0.25),
                (CLAP,    [1.0, 3.0],           0.9, 0.25),
                (OPEN_HAT,[0.5, 1.5, 2.5, 3.5], 0.6, 0.25),
                (HIHAT,   [i * 0.25 for i in range(16)], 0.5, 0.0625),
            ],
            "hiphop": [
                (KICK,    [0.0, 0.75, 2.0, 2.5], 1.0, 0.25),
                (SNARE,   [1.0, 3.0],           1.0, 0.25),
                (HIHAT,   [i * 0.5 for i in range(8)], 0.65, 0.125),
            ],
            "dnb": [
                (KICK,    [0.0, 1.75],          1.0, 0.25),
                (SNARE,   [1.0, 3.0],           1.0, 0.25),
                (HIHAT,   [i * 0.25 for i in range(16)], 0.6, 0.0625),
            ],
            "halftime": [
                (KICK,    [0.0],                1.0, 0.25),
                (SNARE,   [2.0],                1.0, 0.25),
                (HIHAT,   [i * 0.5 for i in range(8)], 0.6, 0.125),
            ],
            "jazz_ride": [
                (RIDE,    [0.0, 0.67, 1.0, 1.67, 2.0, 2.67, 3.0, 3.67], 0.7, 0.25),
                (KICK,    [0.0, 2.5],           0.5, 0.25),
                (HIHAT,   [1.0, 3.0],           0.4, 0.125),
            ],
            "latin": [
                (KICK,    [0.0, 1.5, 3.0],      1.0, 0.25),
                (RIM,     [0.5, 1.0, 2.5, 3.0], 0.8, 0.125),
                (HIHAT,   [i * 0.25 for i in range(16)], 0.5, 0.0625),
                (OPEN_HAT,[1.5, 3.5],           0.7, 0.25),
            ],
            "trap": [
                (KICK,    [0.0, 0.75, 2.0],     1.0, 0.25),
                (SNARE,   [1.0, 3.0],           1.0, 0.25),
                (HIHAT,   [i * 0.125 for i in range(32)], 0.55, 0.0625),
                (OPEN_HAT,[1.75, 3.75],         0.7, 0.125),
            ],
        }

        if style not in patterns:
            raise ValueError(f"Unknown style '{style}'. Available: {', '.join(patterns.keys())}")

        notes = []
        swing_offset = swing * 0.08  # max 80ms-ish swing

        for pitch, positions, vel_ratio, duration in patterns[style]:
            for pos in positions:
                if pos >= clip_length:
                    continue
                actual_pos = pos
                # Apply swing to offbeat 16th notes
                if swing > 0 and (pos * 4) % 2 == 1:
                    actual_pos += swing_offset

                notes.append({
                    "pitch": pitch,
                    "start_time": actual_pos,
                    "duration": duration,
                    "velocity": max(1, min(127, int(velocity * vel_ratio))),
                })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {style} drum pattern with {len(notes)} hits on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("generating euclidean rhythm")
    def euclidean_rhythm(ctx: Context, track_index: int, clip_index: int,
                            hits: int = 5, steps: int = 8, pitch: int = 36,
                            rotation: int = 0, note_length: float = 0.5,
                            velocity: int = 100) -> str:
        """Generate a Euclidean rhythm pattern and write it to a MIDI clip.

        Euclidean rhythms distribute N hits as evenly as possible across M steps.
        Many traditional rhythms (Tresillo, Son clave, Bossa nova) are Euclidean.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - hits: Number of active hits (default: 5)
        - steps: Total number of steps (default: 8)
        - pitch: MIDI note (default: 36 = kick)
        - rotation: Rotate the pattern by N steps (default: 0)
        - note_length: Duration of each step in beats (default: 0.5 = 8th notes)
        - velocity: Note velocity (default: 100)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)

        if hits > steps:
            raise ValueError(f"hits ({hits}) cannot exceed steps ({steps})")
        if steps < 1:
            raise ValueError("steps must be >= 1")

        # Bjorklund algorithm
        def bjorklund(hits, steps):
            if hits == 0:
                return [0] * steps
            if hits == steps:
                return [1] * steps

            groups = [[1] for _ in range(hits)] + [[0] for _ in range(steps - hits)]
            while True:
                remainder = len(groups) - hits
                if remainder <= 1:
                    break
                new_groups = []
                take = min(hits, remainder)
                for i in range(take):
                    new_groups.append(groups[i] + groups[hits + i])
                for i in range(take, hits):
                    new_groups.append(groups[i])
                for i in range(hits + take, len(groups)):
                    new_groups.append(groups[i])
                groups = new_groups
                hits = take if take < hits else hits

            pattern = []
            for g in groups:
                pattern.extend(g)
            return pattern

        pattern = bjorklund(hits, steps)

        # Apply rotation
        if rotation != 0:
            r = rotation % len(pattern)
            pattern = pattern[r:] + pattern[:r]

        notes = []
        for i, active in enumerate(pattern):
            if active:
                notes.append({
                    "pitch": int(pitch),
                    "start_time": i * note_length,
                    "duration": note_length * 0.8,
                    "velocity": int(velocity),
                })

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        pattern_str = "".join("x" if p else "." for p in pattern)
        return f"Generated Euclidean rhythm E({hits},{steps}) [{pattern_str}] with {len(notes)} notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("generating bass line")
    def generate_bass_line(ctx: Context, track_index: int, clip_index: int,
                              root: int = 36, scale_name: str = "minor",
                              pattern_type: str = "root_fifth",
                              note_length: float = 0.5,
                              clip_length: float = 4.0,
                              velocity: int = 100,
                              octave_range: int = 1) -> str:
        """Generate a bass line pattern following a root note and scale.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (clip must exist)
        - root: Root MIDI note (default: 36 = C2)
        - scale_name: "major", "minor", "dorian", "mixolydian", "pentatonic", "blues"
        - pattern_type:
            "root_fifth" -- alternates root and fifth
            "walking" -- stepwise walking bass
            "octave" -- root with octave jumps
            "arpeggiated" -- arpeggiate chord tones
            "syncopated" -- syncopated funk-style pattern
        - note_length: Duration per note in beats (default: 0.5)
        - clip_length: Total clip length in beats (default: 4.0)
        - velocity: Base velocity (default: 100)
        - octave_range: Octave range above root (default: 1)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(velocity, "velocity", 1, 127)
        import random

        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "dorian": [0, 2, 3, 5, 7, 9, 10],
            "mixolydian": [0, 2, 4, 5, 7, 9, 10],
            "pentatonic": [0, 3, 5, 7, 10],
            "blues": [0, 3, 5, 6, 7, 10],
        }
        if scale_name not in scales:
            raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(scales.keys())}")

        intervals = scales[scale_name]
        pitches = []
        for oct in range(octave_range + 1):
            for iv in intervals:
                p = root + oct * 12 + iv
                if 0 <= p <= 127:
                    pitches.append(p)

        total_steps = int(clip_length / note_length)
        notes = []

        if pattern_type == "root_fifth":
            fifth = root + 7
            for i in range(total_steps):
                p = root if i % 2 == 0 else fifth
                notes.append({"pitch": p, "start_time": i * note_length,
                              "duration": note_length * 0.9, "velocity": int(velocity)})
        elif pattern_type == "walking":
            idx = 0
            direction = 1
            for i in range(total_steps):
                notes.append({"pitch": pitches[idx], "start_time": i * note_length,
                              "duration": note_length * 0.9, "velocity": int(velocity)})
                idx += direction
                if idx >= len(pitches) - 1:
                    direction = -1
                elif idx <= 0:
                    direction = 1
        elif pattern_type == "octave":
            for i in range(total_steps):
                p = root if i % 2 == 0 else root + 12
                notes.append({"pitch": max(0, min(127, p)), "start_time": i * note_length,
                              "duration": note_length * 0.8, "velocity": int(velocity)})
        elif pattern_type == "arpeggiated":
            chord_tones = [pitches[0], pitches[2] if len(pitches) > 2 else pitches[0],
                           pitches[4] if len(pitches) > 4 else pitches[-1]]
            for i in range(total_steps):
                p = chord_tones[i % len(chord_tones)]
                notes.append({"pitch": p, "start_time": i * note_length,
                              "duration": note_length * 0.8, "velocity": int(velocity)})
        elif pattern_type == "syncopated":
            positions = [0.0, 0.75, 1.5, 2.0, 2.75, 3.5]
            for pos in positions:
                if pos >= clip_length:
                    continue
                p = random.choice(pitches[:5]) if len(pitches) >= 5 else random.choice(pitches)
                notes.append({"pitch": p, "start_time": pos,
                              "duration": note_length * 0.9,
                              "velocity": max(1, min(127, int(velocity * random.uniform(0.8, 1.0))))})
        else:
            raise ValueError(f"Unknown pattern_type '{pattern_type}'")

        ableton = get_ableton_connection()
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Generated {pattern_type} bass line ({scale_name}) with {len(notes)} notes on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("harmonizing melody")
    def harmonize_melody(ctx: Context, track_index: int, clip_index: int,
                            interval: str = "3rd", scale_name: str = "major",
                            root: int = 60, direction: str = "below") -> str:
        """Add harmony notes to an existing melody, constrained to a scale.

        Reads existing notes from the clip and adds a harmony note for each,
        snapped to the nearest scale degree at the specified interval.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index (must contain MIDI notes)
        - interval: Harmony interval: "3rd", "5th", "6th", "octave"
        - scale_name: "major", "minor", "dorian", "mixolydian", "harmonic_minor"
        - root: Root note of the scale (default: 60 = C4)
        - direction: "below" (harmony below melody) or "above"
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")

        interval_map = {"3rd": 2, "5th": 4, "6th": 5, "octave": 7}
        if interval not in interval_map:
            raise ValueError(f"Unknown interval '{interval}'. Available: {', '.join(interval_map.keys())}")

        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "dorian": [0, 2, 3, 5, 7, 9, 10],
            "mixolydian": [0, 2, 4, 5, 7, 9, 10],
            "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        }
        if scale_name not in scales:
            raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(scales.keys())}")

        intervals = scales[scale_name]
        scale_degrees = interval_map[interval]

        # Build full pitch->scale_degree lookup
        def pitch_to_scale_index(pitch):
            pc = (pitch - root) % 12
            # Find closest scale tone
            best = min(intervals, key=lambda x: abs(x - pc))
            return intervals.index(best)

        def scale_index_to_pitch(pitch, offset):
            pc = (pitch - root) % 12
            octave = (pitch - root) // 12
            idx = pitch_to_scale_index(pitch)

            new_idx = idx + (offset if direction == "above" else -offset)
            new_octave = octave + new_idx // len(intervals)
            new_idx = new_idx % len(intervals)

            return root + new_octave * 12 + intervals[new_idx]

        ableton = get_ableton_connection()
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": track_index, "clip_index": clip_index,
            "start_time": 0.0, "time_span": 0.0,
            "start_pitch": 0, "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found to harmonize"

        harmony_notes = []
        for note in notes:
            harmony_pitch = scale_index_to_pitch(note["pitch"], scale_degrees)
            harmony_pitch = max(0, min(127, harmony_pitch))
            harmony_notes.append({
                "pitch": harmony_pitch,
                "start_time": note["start_time"],
                "duration": note["duration"],
                "velocity": max(1, int(note["velocity"] * 0.85)),
            })

        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": harmony_notes,
        })

        return f"Added {len(harmony_notes)} harmony notes ({interval} {direction}, {scale_name}) on track {track_index} clip {clip_index}"


    @mcp.tool()
    @_tool_handler("quantizing notes to scale")
    def quantize_to_scale(ctx: Context, track_index: int, clip_index: int,
                             root: int = 60, scale_name: str = "major") -> str:
        """Snap all notes in a MIDI clip to the nearest note in a musical scale.

        Out-of-scale notes are moved to the closest scale degree. Notes already
        in the scale are left unchanged.

        Parameters:
        - track_index: The MIDI track index
        - clip_index: The clip slot index
        - root: Root note of the scale (default: 60 = C4, only the pitch class matters)
        - scale_name: "major", "minor", "dorian", "mixolydian", "pentatonic", "blues", "harmonic_minor", "chromatic"
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")

        scales = {
            "major": [0, 2, 4, 5, 7, 9, 11],
            "minor": [0, 2, 3, 5, 7, 8, 10],
            "dorian": [0, 2, 3, 5, 7, 9, 10],
            "mixolydian": [0, 2, 4, 5, 7, 9, 10],
            "pentatonic": [0, 2, 4, 7, 9],
            "blues": [0, 3, 5, 6, 7, 10],
            "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
            "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        }
        if scale_name not in scales:
            raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(scales.keys())}")

        intervals = scales[scale_name]
        root_pc = root % 12

        def snap_to_scale(pitch):
            pc = pitch % 12
            relative_pc = (pc - root_pc) % 12
            if relative_pc in intervals:
                return pitch
            # Find closest scale tone
            best = min(intervals, key=lambda x: min(abs(x - relative_pc), 12 - abs(x - relative_pc)))
            diff = best - relative_pc
            if abs(diff) > 6:
                diff = diff - 12 if diff > 0 else diff + 12
            return max(0, min(127, pitch + diff))

        ableton = get_ableton_connection()
        clip_notes = ableton.send_command("get_clip_notes", {
            "track_index": track_index, "clip_index": clip_index,
            "start_time": 0.0, "time_span": 0.0,
            "start_pitch": 0, "pitch_span": 128,
        })

        notes = clip_notes.get("notes", [])
        if not notes:
            return "No notes found to quantize"

        # Remove old notes, add corrected ones
        ableton.send_command("remove_notes_range", {
            "track_index": track_index, "clip_index": clip_index,
            "from_time": 0.0, "time_span": 999999.0,
            "from_pitch": 0, "pitch_span": 128,
        })

        corrected = 0
        for note in notes:
            new_pitch = snap_to_scale(note["pitch"])
            if new_pitch != note["pitch"]:
                corrected += 1
                note["pitch"] = new_pitch

        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        return f"Quantized {corrected} out-of-scale notes (of {len(notes)} total) to {scale_name} (root {root_pc}) on track {track_index} clip {clip_index}"
