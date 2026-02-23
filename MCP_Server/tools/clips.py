"""Clip tool handlers for AbletonBridge."""
import json
from typing import List, Dict, Union, Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_index_allow_negative, _validate_range, _validate_notes


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("creating clip")
    def create_clip(ctx: Context, track_index: int, clip_index: int, length: float = 4.0) -> str:
        """
        Create a new MIDI clip in the specified track and clip slot.

        Parameters:
        - track_index: The index of the track to create the clip in
        - clip_index: The index of the clip slot to create the clip in
        - length: The length of the clip in beats (default: 4.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if not isinstance(length, (int, float)) or isinstance(length, bool) or length <= 0:
            raise ValueError(f"length must be a positive number, got {length}.")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "length": length
        })
        return f"Created new clip at track {track_index}, slot {clip_index} with length {length} beats"

    @mcp.tool()
    @_tool_handler("deleting clip")
    def delete_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Delete a clip from a clip slot.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Deleted clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("getting clip info")
    def get_clip_info(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Get detailed information about a clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_info", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("clearing clip notes")
    def clear_clip_notes(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Remove all MIDI notes from a clip without deleting the clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Cleared {result.get('notes_removed', 0)} notes from clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("adding notes to clip")
    def add_notes_to_clip(
        ctx: Context,
        track_index: int,
        clip_index: int,
        notes: List[Dict[str, Union[int, float, bool]]]
    ) -> str:
        """
        Add MIDI notes to a clip.

        Standard note adding. Use add_notes_extended when you need to set
        probability or velocity deviation (Live 11+).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - notes: List of note dictionaries, each with pitch, start_time, duration, velocity, and mute
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_notes(notes)
        ableton = get_ableton_connection()
        result = ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes
        })
        return f"Added {len(notes)} notes to clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("adding extended notes")
    def add_notes_extended(ctx: Context, track_index: int, clip_index: int,
                           notes: List[Dict]) -> str:
        """
        Add MIDI notes with Live 11+ extended properties.

        Use instead of add_notes_to_clip when you need to set probability,
        velocity_deviation, or release_velocity on notes.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - notes: List of note dictionaries with:
            - pitch (int): MIDI note number (0-127)
            - start_time (float): Start position in beats
            - duration (float): Note duration in beats
            - velocity (int): Note velocity (1-127)
            - mute (bool): Whether the note is muted (optional, default false)
            - probability (float): Note trigger probability 0.0-1.0 (Live 11+, optional)
            - velocity_deviation (float): Random velocity range -127 to 127 (Live 11+, optional)
            - release_velocity (int): Note release velocity 0-127 (Live 11+, optional)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if not notes:
            return "No notes provided"
        ableton = get_ableton_connection()
        result = ableton.send_command("add_notes_extended", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })
        ext = " (with extended properties)" if result.get("extended") else ""
        return f"Added {result.get('note_count', 0)} notes to clip{ext}"

    @mcp.tool()
    @_tool_handler("getting clip notes")
    def get_clip_notes(ctx: Context, track_index: int, clip_index: int,
                       start_time: float = 0.0, time_span: float = 0.0,
                       start_pitch: int = 0, pitch_span: int = 128) -> str:
        """
        Get MIDI notes from a clip.

        Basic note reading without note IDs. For probability/velocity deviation
        data, use get_notes_extended. For in-place editing with stable note IDs,
        use get_clip_notes_with_ids (requires M4L bridge).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - start_time: Start time in beats (default: 0.0)
        - time_span: Duration in beats to retrieve (default: 0.0 = entire clip)
        - start_pitch: Lowest MIDI pitch to retrieve (default: 0)
        - pitch_span: Range of pitches to retrieve (default: 128 = all pitches)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(start_pitch, "start_pitch", 0, 127)
        _validate_range(pitch_span, "pitch_span", 1, 128)
        if start_time < 0:
            raise ValueError(f"start_time must be non-negative, got {start_time}.")
        if time_span < 0:
            raise ValueError(f"time_span must be non-negative, got {time_span}.")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "start_time": start_time,
            "time_span": time_span,
            "start_pitch": start_pitch,
            "pitch_span": pitch_span
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting extended notes")
    def get_notes_extended(ctx: Context, track_index: int, clip_index: int,
                           start_time: float = 0.0, time_span: float = 0.0) -> str:
        """
        Get MIDI notes with Live 11+ extended properties (probability, velocity_deviation, release_velocity).

        Use instead of get_clip_notes when you need probability, velocity_deviation,
        or release_velocity data. Does not include stable note IDs -- for that, use
        get_clip_notes_with_ids (requires M4L bridge).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - start_time: Start time in beats (default: 0.0)
        - time_span: Duration in beats to retrieve (default: 0.0 = entire clip)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_notes_extended", {
            "track_index": track_index,
            "clip_index": clip_index,
            "start_time": start_time,
            "time_span": time_span,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("removing notes range")
    def remove_notes_range(ctx: Context, track_index: int, clip_index: int,
                           from_time: float = 0.0, time_span: float = 0.0,
                           from_pitch: int = 0, pitch_span: int = 128) -> str:
        """
        Selectively remove MIDI notes within a specific time and pitch range.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - from_time: Start time in beats (default: 0.0)
        - time_span: Time range in beats (default: 0.0 = entire clip)
        - from_pitch: Lowest MIDI pitch to remove (default: 0)
        - pitch_span: Range of pitches to remove (default: 128 = all)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("remove_notes_range", {
            "track_index": track_index,
            "clip_index": clip_index,
            "from_time": from_time,
            "time_span": time_span,
            "from_pitch": from_pitch,
            "pitch_span": pitch_span,
        })
        return f"Removed {result.get('notes_removed', 0)} notes from range (time={from_time}-{from_time+time_span}, pitch={from_pitch}-{from_pitch+pitch_span})"

    @mcp.tool()
    @_tool_handler("duplicating clip")
    def duplicate_clip(ctx: Context, track_index: int, clip_index: int, target_clip_index: int) -> str:
        """
        Duplicate a clip to another clip slot on the same track.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the source clip slot
        - target_clip_index: The index of the target clip slot
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_index(target_clip_index, "target_clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "target_clip_index": target_clip_index
        })
        return f"Duplicated clip from slot {clip_index} to slot {target_clip_index} on track {track_index}"

    @mcp.tool()
    @_tool_handler("duplicating clip loop")
    def duplicate_clip_loop(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Double the loop content of a clip (e.g., 4 bars becomes 8 bars with content repeated).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip_loop", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return (f"Doubled loop of clip '{result.get('clip_name', '')}' -- "
                f"{result.get('old_length', '?')} -> {result.get('new_length', '?')} beats")

    @mcp.tool()
    @_tool_handler("duplicating clip region")
    def duplicate_clip_region(ctx: Context, track_index: int, clip_index: int,
                               region_start: float, region_length: float,
                               destination_time: float, pitch: int = -1,
                               transposition_amount: int = 0) -> str:
        """Duplicate notes in a MIDI clip region to another position, with optional transposition.

        Parameters:
        - track_index: Track containing the clip
        - clip_index: The MIDI clip slot index
        - region_start: Start time of the region to duplicate (in beats)
        - region_length: Length of the region to duplicate (in beats)
        - destination_time: Where to place the duplicated notes (in beats)
        - pitch: Only duplicate notes at this MIDI pitch (-1 for all notes). Default: -1
        - transposition_amount: Semitones to transpose the duplicated notes. Default: 0
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip_region", {
            "track_index": track_index,
            "clip_index": clip_index,
            "region_start": region_start,
            "region_length": region_length,
            "destination_time": destination_time,
            "pitch": pitch,
            "transposition_amount": transposition_amount,
        })
        return f"Duplicated region [{region_start}-{region_start + region_length}] to time {destination_time} (transpose: {transposition_amount} semitones)"

    @mcp.tool()
    @_tool_handler("setting clip name")
    def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> str:
        """
        Set the name of a clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - name: The new name for the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_name", {
            "track_index": track_index,
            "clip_index": clip_index,
            "name": name
        })
        return f"Renamed clip at track {track_index}, slot {clip_index} to '{name}'"

    @mcp.tool()
    @_tool_handler("setting clip color")
    def set_clip_color(ctx: Context, track_index: int, clip_index: int, color_index: int) -> str:
        """
        Set the color of a clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - color_index: The color index (0-69, Ableton's color palette)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(color_index, "color_index", 0, 69)
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_color", {
            "track_index": track_index,
            "clip_index": clip_index,
            "color_index": color_index
        })
        return f"Set color index to {result.get('color_index', color_index)} for clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("setting clip looping")
    def set_clip_looping(ctx: Context, track_index: int, clip_index: int, looping: bool) -> str:
        """
        Set the looping state of a clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - looping: True to enable looping, False to disable
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_looping", {
            "track_index": track_index,
            "clip_index": clip_index,
            "looping": looping
        })
        state = "enabled" if result.get('looping', looping) else "disabled"
        return f"Looping {state} for clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("setting clip loop points")
    def set_clip_loop_points(ctx: Context, track_index: int, clip_index: int,
                              loop_start: float, loop_end: float) -> str:
        """
        Set the LOOP region start and end points of a clip.

        Sets the loop boundaries (the region that repeats when looping is enabled).
        Different from set_clip_start_end which sets playback start/end markers.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - loop_start: The loop start position in beats
        - loop_end: The loop end position in beats
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if loop_start < 0:
            raise ValueError(f"loop_start must be non-negative, got {loop_start}.")
        if loop_end < 0:
            raise ValueError(f"loop_end must be non-negative, got {loop_end}.")
        if loop_end <= loop_start:
            raise ValueError(f"loop_end ({loop_end}) must be greater than loop_start ({loop_start}).")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_loop_points", {
            "track_index": track_index,
            "clip_index": clip_index,
            "loop_start": loop_start,
            "loop_end": loop_end
        })
        return f"Set loop points for clip at track {track_index}, slot {clip_index}: start={result.get('loop_start', loop_start)}, end={result.get('loop_end', loop_end)}"

    @mcp.tool()
    @_tool_handler("setting clip start/end markers")
    def set_clip_start_end(ctx: Context, track_index: int, clip_index: int,
                           start_marker: float = None, end_marker: float = None) -> str:
        """
        Set clip start_marker and end_marker positions (controls playback region without changing notes).

        Sets the playback START/END markers, which are separate from the loop region.
        Different from set_clip_loop_points which sets the loop boundaries.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - start_marker: The new start marker position in beats (optional)
        - end_marker: The new end marker position in beats (optional)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if start_marker is not None:
            params["start_marker"] = start_marker
        if end_marker is not None:
            params["end_marker"] = end_marker
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_start_end", params)
        return (f"Clip '{result.get('clip_name', '')}' markers set -- "
                f"start: {result.get('start_marker', '?')}, end: {result.get('end_marker', '?')}")

    @mcp.tool()
    @_tool_handler("setting clip start time")
    def set_clip_start_time(ctx: Context, track_index: int, clip_index: int, time: float) -> str:
        """Set the start time (position) of a clip in the arrangement.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - time: The new start time in beats
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_start_time", {
            "track_index": track_index,
            "clip_index": clip_index,
            "time": time,
        })
        return f"Set clip start time to {result.get('start_time', time)} beats"

    @mcp.tool()
    @_tool_handler("quantizing clip notes")
    def quantize_clip_notes(ctx: Context, track_index: int, clip_index: int, grid_size: float = 0.25) -> str:
        """
        Quantize MIDI notes in a clip to snap to a grid.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - grid_size: The grid size in beats (0.25 = 16th notes, 0.5 = 8th notes, 1.0 = quarter notes)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if not isinstance(grid_size, (int, float)) or isinstance(grid_size, bool) or grid_size <= 0:
            raise ValueError(f"grid_size must be a positive number, got {grid_size}.")
        ableton = get_ableton_connection()
        result = ableton.send_command("quantize_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "grid_size": grid_size
        })
        return f"Quantized {result.get('notes_quantized', 0)} notes to {grid_size} beat grid in clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("transposing clip notes")
    def transpose_clip_notes(ctx: Context, track_index: int, clip_index: int, semitones: int) -> str:
        """
        Transpose all MIDI notes in a clip by a number of semitones.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - semitones: The number of semitones to transpose (positive = up, negative = down)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(semitones, "semitones", -127, 127)
        ableton = get_ableton_connection()
        result = ableton.send_command("transpose_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "semitones": semitones
        })
        direction = "up" if semitones > 0 else "down"
        return f"Transposed {result.get('notes_transposed', 0)} notes {direction} by {abs(semitones)} semitones in clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("cropping clip")
    def crop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Trim a clip to its current loop region, discarding content outside.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("crop_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return f"Cropped clip '{result.get('clip_name', '')}' -- new length: {result.get('new_length', '?')} beats"

    @mcp.tool()
    @_tool_handler("reversing clip")
    def reverse_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """Reverse an audio clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("reverse_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return f"Clip reversed: {result.get('reversed', True)}"

    @mcp.tool()
    @_tool_handler("firing clip")
    def fire_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Launch a clip in Session View. The clip starts from its beginning (or loop
        start). For arrangement playback, use start_playback instead.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("fire_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Started playing clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("stopping clip")
    def stop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        Stop a clip in Session View. For stopping all playback, use stop_playback
        instead.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("stop_clip", {
            "track_index": track_index,
            "clip_index": clip_index
        })
        return f"Stopped clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("setting clip pitch")
    def set_clip_pitch(ctx: Context, track_index: int, clip_index: int,
                       pitch_coarse: int = None, pitch_fine: float = None) -> str:
        """Set pitch transposition for an audio clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - pitch_coarse: Semitones shift (-48 to +48). Optional.
        - pitch_fine: Cents shift (-50.0 to +50.0). Optional.

        Only works on audio clips (not MIDI). Useful for tuning samples,
        creating harmonies, or pitch-correcting audio.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if pitch_coarse is not None:
            params["pitch_coarse"] = pitch_coarse
        if pitch_fine is not None:
            params["pitch_fine"] = pitch_fine
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_pitch", params)
        return f"Clip '{result.get('clip_name', '?')}' pitch set to {result.get('pitch_coarse', 0)} semitones, {result.get('pitch_fine', 0)} cents"

    @mcp.tool()
    @_tool_handler("setting clip launch mode")
    def set_clip_launch_mode(ctx: Context, track_index: int, clip_index: int,
                             launch_mode: int) -> str:
        """Set the launch mode for a clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - launch_mode: 0=trigger (default), 1=gate (plays while held), 2=toggle, 3=repeat

        Controls how the clip responds to launch triggers in session view.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        mode_names = {0: "trigger", 1: "gate", 2: "toggle", 3: "repeat"}
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_launch_mode", {
            "track_index": track_index,
            "clip_index": clip_index,
            "launch_mode": launch_mode,
        })
        mode_name = mode_names.get(result.get("launch_mode", launch_mode), "unknown")
        return f"Clip '{result.get('clip_name', '?')}' launch mode set to {mode_name}"

    @mcp.tool()
    @_tool_handler("setting clip launch quantization")
    def set_clip_launch_quantization(ctx: Context, track_index: int, clip_index: int,
                                      quantization: int) -> str:
        """Set when a clip starts playing after being triggered.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - quantization: 0=none, 1=8_bars, 2=4_bars, 3=2_bars, 4=bar, 5=half,
          6=half_triplet, 7=quarter, 8=quarter_triplet, 9=eighth, 10=eighth_triplet,
          11=sixteenth, 12=sixteenth_triplet, 13=thirtysecond, 14=global

        Overrides the global launch quantization for this specific clip.
        Use 14 to follow the song's global launch quantization setting.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_range(quantization, "quantization", 0, 14)
        quant_names = {
            0: "none", 1: "8 bars", 2: "4 bars", 3: "2 bars", 4: "1 bar",
            5: "1/2", 6: "1/2T", 7: "1/4", 8: "1/4T", 9: "1/8", 10: "1/8T",
            11: "1/16", 12: "1/16T", 13: "1/32", 14: "global",
        }
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_launch_quantization", {
            "track_index": track_index,
            "clip_index": clip_index,
            "quantization": quantization,
        })
        q_name = quant_names.get(result.get("launch_quantization", quantization), "unknown")
        return f"Clip '{result.get('clip_name', '?')}' launch quantization set to {q_name}"

    @mcp.tool()
    @_tool_handler("setting clip legato")
    def set_clip_legato(ctx: Context, track_index: int, clip_index: int,
                         legato: bool) -> str:
        """Enable or disable legato mode for a clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - legato: True = clip plays from the position of the previously playing clip
                  (seamless transition). False = clip starts from its start position.

        Legato mode is useful for live performance, allowing smooth transitions
        between clips without resetting to the beginning.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_legato", {
            "track_index": track_index,
            "clip_index": clip_index,
            "legato": legato,
        })
        state = "enabled" if result.get("legato", legato) else "disabled"
        return f"Clip '{result.get('clip_name', '?')}' legato {state}"

    @mcp.tool()
    @_tool_handler("setting clip warp")
    def set_clip_warp(ctx: Context, track_index: int, clip_index: int, warping_enabled: bool) -> str:
        """Enable or disable warping for an audio clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - warping_enabled: True to enable warping, False to disable
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_warp", {
            "track_index": track_index,
            "clip_index": clip_index,
            "warping_enabled": warping_enabled,
        })
        return f"Warping {'enabled' if result.get('warping', warping_enabled) else 'disabled'}"

    @mcp.tool()
    @_tool_handler("setting warp mode")
    def set_warp_mode(ctx: Context, track_index: int, clip_index: int, warp_mode: str) -> str:
        """Set the warp mode for an audio clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - warp_mode: The warp mode (beats, tones, texture, re_pitch, complex, complex_pro)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_warp_mode", {
            "track_index": track_index,
            "clip_index": clip_index,
            "warp_mode": warp_mode,
        })
        return f"Warp mode set to {result.get('warp_mode', warp_mode)}"

    @mcp.tool()
    @_tool_handler("duplicating clip to arrangement")
    def duplicate_clip_to_arrangement(ctx: Context, track_index: int, clip_index: int, time: float) -> str:
        """
        Copy a session clip to the arrangement timeline at a given beat position.

        This is the primary arrangement workflow tool -- build clips in session view,
        then place them on the arrangement timeline.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - time: The beat position on the arrangement timeline to place the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip_to_arrangement", {
            "track_index": track_index,
            "clip_index": clip_index,
            "time": time,
        })
        return (f"Placed clip '{result.get('clip_name', '')}' on arrangement at beat {result.get('placed_at', time)} "
                f"(track {track_index}, length {result.get('clip_length', '?')} beats)")

    @mcp.tool()
    @_tool_handler("setting clip grid")
    def set_clip_grid(ctx: Context, track_index: int, clip_index: int,
                       grid_quantization: int = None, grid_is_triplet: bool = None) -> str:
        """Set the MIDI editor grid resolution for a clip.

        Parameters:
        - track_index: Track containing the clip
        - clip_index: The clip slot index
        - grid_quantization: Grid resolution enum value. Optional.
        - grid_is_triplet: True for triplet grid, False for standard. Optional.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if grid_quantization is not None:
            params["grid_quantization"] = grid_quantization
        if grid_is_triplet is not None:
            params["grid_is_triplet"] = grid_is_triplet
        if len(params) == 2:
            return "No parameters specified. Provide grid_quantization and/or grid_is_triplet."
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_grid", params)
        changes = [f"{k}={v}" for k, v in result.items()
                   if k not in ("track_index", "clip_index")]
        return f"Clip grid updated: {', '.join(changes)}"

    @mcp.tool()
    @_tool_handler("moving clip playing position")
    def move_clip_playing_pos(ctx: Context, track_index: int, clip_index: int,
                               time: float) -> str:
        """Jump to a position within a currently playing clip.

        Parameters:
        - track_index: Track containing the clip
        - clip_index: The clip slot index
        - time: The time position to jump to within the clip (in beats)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("move_clip_playing_pos", {
            "track_index": track_index,
            "clip_index": clip_index,
            "time": time,
        })
        return f"Moved clip playing position to {time}"

    @mcp.tool()
    @_tool_handler("getting clip follow actions")
    def get_clip_follow_actions(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get the follow action settings for a clip.

        Returns follow_action_0, follow_action_1, probability, time, enabled, linked,
        and return_to_zero settings.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_follow_actions", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting clip follow actions")
    def set_clip_follow_actions(ctx: Context, track_index: int, clip_index: int,
                                 follow_action_0: int = None, follow_action_1: int = None,
                                 follow_action_probability: float = None,
                                 follow_action_time: float = None,
                                 follow_action_enabled: bool = None,
                                 follow_action_linked: bool = None,
                                 follow_action_return_to_zero: bool = None) -> str:
        """Set follow action settings for a clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - follow_action_0: First follow action type (0=None, 1=Stop, 2=Again, 3=Previous, 4=Next, 5=First, 6=Last, 7=Any, 8=Other, 9=Jump)
        - follow_action_1: Second follow action type (same values as above)
        - follow_action_probability: Probability of action A vs B (0.0 to 1.0)
        - follow_action_time: Time before follow action triggers (in beats)
        - follow_action_enabled: Whether follow actions are enabled
        - follow_action_linked: Whether follow actions are linked to clip end
        - follow_action_return_to_zero: Whether to return to clip start after follow action
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if follow_action_0 is not None:
            params["follow_action_0"] = follow_action_0
        if follow_action_1 is not None:
            params["follow_action_1"] = follow_action_1
        if follow_action_probability is not None:
            _validate_range(follow_action_probability, "follow_action_probability", 0.0, 1.0)
            params["follow_action_probability"] = follow_action_probability
        if follow_action_time is not None:
            params["follow_action_time"] = follow_action_time
        if follow_action_enabled is not None:
            params["follow_action_enabled"] = follow_action_enabled
        if follow_action_linked is not None:
            params["follow_action_linked"] = follow_action_linked
        if follow_action_return_to_zero is not None:
            params["follow_action_return_to_zero"] = follow_action_return_to_zero
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_follow_actions", params)
        changed = result.get("changed", [])
        return f"Updated follow actions on track {track_index} clip {clip_index}: {', '.join(changed) if changed else 'no changes'}"

    @mcp.tool()
    @_tool_handler("getting clip properties")
    def get_clip_properties(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get extended properties of a clip including follow actions, ram_mode, groove, signature, etc.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_properties", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting clip properties")
    def set_clip_properties(ctx: Context, track_index: int, clip_index: int,
                             muted: bool = None, velocity_amount: float = None,
                             groove: str = None, signature_numerator: int = None,
                             signature_denominator: int = None, ram_mode: bool = None,
                             warping: bool = None, gain: float = None) -> str:
        """Set multiple clip properties at once.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - muted: Whether the clip is muted
        - velocity_amount: Velocity scaling (0.0 to 1.0)
        - groove: Groove name to assign
        - signature_numerator: Time signature numerator
        - signature_denominator: Time signature denominator
        - ram_mode: Whether to load clip into RAM (audio clips only)
        - warping: Whether warping is enabled (audio clips only)
        - gain: Audio clip gain (0.0 to 1.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if muted is not None:
            params["muted"] = muted
        if velocity_amount is not None:
            _validate_range(velocity_amount, "velocity_amount", 0.0, 1.0)
            params["velocity_amount"] = velocity_amount
        if groove is not None:
            params["groove"] = groove
        if signature_numerator is not None:
            params["signature_numerator"] = signature_numerator
        if signature_denominator is not None:
            params["signature_denominator"] = signature_denominator
        if ram_mode is not None:
            params["ram_mode"] = ram_mode
        if warping is not None:
            params["warping"] = warping
        if gain is not None:
            _validate_range(gain, "gain", 0.0, 1.0)
            params["gain"] = gain
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_properties", params)
        changed = result.get("changed", [])
        return f"Updated clip properties on track {track_index} clip {clip_index}: {', '.join(changed) if changed else 'no changes'}"

    @mcp.tool()
    @_tool_handler("selecting all notes")
    def select_all_notes(ctx: Context, track_index: int, clip_index: int) -> str:
        """Select all notes in a MIDI clip.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("select_all_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return f"Selected all notes in clip at track {track_index}, slot {clip_index}"

    @mcp.tool()
    @_tool_handler("deselecting all notes")
    def deselect_all_notes(ctx: Context, track_index: int, clip_index: int) -> str:
        """Deselect all notes in a MIDI clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("deselect_all_notes", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting selected notes")
    def get_selected_notes(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get the currently UI-selected notes in a MIDI clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_selected_notes", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("stopping track clips")
    def stop_track_clips(ctx: Context, track_index: int) -> str:
        """Stop all clips playing on a specific track.

        Parameters:
        - track_index: The index of the track
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("stop_track_clips", {"track_index": track_index})
        return f"Stopped all clips on track {track_index}"

    @mcp.tool()
    @_tool_handler("capturing MIDI")
    def capture_midi(ctx: Context) -> str:
        """Capture recently played MIDI notes (requires Live 11 or later)."""
        ableton = get_ableton_connection()
        result = ableton.send_command("capture_midi")
        return "MIDI captured successfully"

    @mcp.tool()
    @_tool_handler("getting playing clips")
    def get_playing_clips(ctx: Context) -> str:
        """Get all currently playing and triggered clips across all tracks.
        Returns track index, clip index, clip name, and status (playing/triggered) for each active clip."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_playing_clips", {})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting warp markers")
    def get_warp_markers(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get the warp markers of an audio clip. Each marker has a beat_time and sample_time.

        Parameters:
        - track_index: Track containing the audio clip
        - clip_index: Clip slot index
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_warp_markers", {
            "track_index": track_index, "clip_index": clip_index
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("adding warp marker")
    def add_warp_marker(ctx: Context, track_index: int, clip_index: int,
                         beat_time: float, sample_time: float = None) -> str:
        """Add a warp marker to an audio clip for time-stretching control.

        Parameters:
        - track_index: Track containing the audio clip
        - clip_index: Clip slot index
        - beat_time: Beat position for the warp marker
        - sample_time: Sample position (optional, auto-calculated by Live if omitted)
        """
        params = {"track_index": track_index, "clip_index": clip_index, "beat_time": beat_time}
        if sample_time is not None:
            params["sample_time"] = sample_time
        ableton = get_ableton_connection()
        result = ableton.send_command("add_warp_marker", params)
        return f"Warp marker added at beat {beat_time}"

    @mcp.tool()
    @_tool_handler("moving warp marker")
    def move_warp_marker(ctx: Context, track_index: int, clip_index: int,
                          beat_time: float, beat_time_distance: float) -> str:
        """Move a warp marker by a beat-time distance.

        Parameters:
        - track_index: Track containing the audio clip
        - clip_index: Clip slot index
        - beat_time: Beat position of the warp marker to move
        - beat_time_distance: Amount (in beats) to shift the marker
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("move_warp_marker", {
            "track_index": track_index, "clip_index": clip_index,
            "beat_time": beat_time, "beat_time_distance": beat_time_distance
        })
        return f"Warp marker at beat {beat_time} moved by {beat_time_distance}"

    @mcp.tool()
    @_tool_handler("removing warp marker")
    def remove_warp_marker(ctx: Context, track_index: int, clip_index: int,
                            beat_time: float) -> str:
        """Remove a warp marker from an audio clip by beat position.

        Parameters:
        - track_index: Track containing the audio clip
        - clip_index: Clip slot index
        - beat_time: Beat position of the warp marker to remove
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("remove_warp_marker", {
            "track_index": track_index, "clip_index": clip_index,
            "beat_time": beat_time
        })
        return f"Warp marker at beat {beat_time} removed"

    # NOTE: get_audio_clip_info and analyze_audio_clip are registered in
    # tools/audio.py (their canonical home)

    @mcp.tool()
    @_tool_handler("setting fire button state")
    def set_fire_button_state(ctx: Context, track_index: int, clip_index: int,
                                state: bool = True) -> str:
        """Set the fire button state of a clip (direct trigger control).

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - state: True to fire, False to release
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_fire_button_state", {
            "track_index": track_index, "clip_index": clip_index,
            "state": state,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("scrubbing clip")
    def clip_scrub_native(ctx: Context, track_index: int, clip_index: int,
                            position: float) -> str:
        """Start scrubbing a clip at the given position via Remote Script.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - position: Beat position to scrub to
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clip_scrub_native", {
            "track_index": track_index, "clip_index": clip_index,
            "position": position,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("stopping clip scrub")
    def clip_stop_scrub(ctx: Context, track_index: int, clip_index: int) -> str:
        """Stop scrubbing a clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clip_stop_scrub", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("converting beat to sample time")
    def clip_beat_to_sample_time(ctx: Context, track_index: int, clip_index: int,
                                    beat_time: float) -> str:
        """Convert beat time to sample time for an audio clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - beat_time: Time in beats to convert
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clip_beat_to_sample_time", {
            "track_index": track_index, "clip_index": clip_index,
            "beat_time": beat_time,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("converting sample to beat time")
    def clip_sample_to_beat_time(ctx: Context, track_index: int, clip_index: int,
                                    sample_time: float) -> str:
        """Convert sample time to beat time for an audio clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - sample_time: Time in samples to convert
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clip_sample_to_beat_time", {
            "track_index": track_index, "clip_index": clip_index,
            "sample_time": sample_time,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("duplicating clip slot")
    def duplicate_clip_slot(ctx: Context, track_index: int, clip_index: int) -> str:
        """Duplicate a clip slot within a track (copy to next free slot).

        Parameters:
        - track_index: The track index
        - clip_index: The source clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_clip_slot", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting clip slot properties")
    def get_clip_slot_properties(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get clip slot properties (has_stop_button, is_group_slot, color, trigger state).

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_slot_properties", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting clip slot properties")
    def set_clip_slot_properties(ctx: Context, track_index: int, clip_index: int,
                                   has_stop_button: Optional[bool] = None,
                                   color_index: Optional[int] = None) -> str:
        """Set clip slot properties (has_stop_button, color).

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - has_stop_button: Enable/disable the stop button on the clip slot
        - color_index: Color index for the clip slot
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        params = {"track_index": track_index, "clip_index": clip_index}
        if has_stop_button is not None:
            params["has_stop_button"] = has_stop_button
        if color_index is not None:
            params["color_index"] = color_index
        ableton = get_ableton_connection()
        result = ableton.send_command("set_clip_slot_properties", params)
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("jumping in running session clip")
    def jump_in_running_session_clip(ctx: Context, track_index: int,
                                        amount: float) -> str:
        """Jump forward/backward in the currently playing session clip on a track.

        Parameters:
        - track_index: The track index
        - amount: Relative jump in beats (positive=forward, negative=backward)
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("jump_in_running_session_clip", {
            "track_index": track_index, "amount": amount,
        })
        return json.dumps(result)
