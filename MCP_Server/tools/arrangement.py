"""Arrangement tool handlers for AbletonBridge."""
import json
from typing import Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_range


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("getting arrangement clips")
    def get_arrangement_clips(ctx: Context, track_index: int) -> str:
        """Get all clips in arrangement view for a track.

        Parameters:
        - track_index: The index of the track to get arrangement clips from
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_arrangement_clips", {"track_index": track_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("deleting time")
    def delete_time(ctx: Context, start_time: float, end_time: float) -> str:
        """Delete a section of time from the arrangement (removes time and shifts everything after).

        Parameters:
        - start_time: Start position in beats
        - end_time: End position in beats
        """
        if start_time >= end_time:
            return "Error: start_time must be less than end_time"
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_time", {
            "start_time": start_time,
            "end_time": end_time,
        })
        return f"Deleted time from {start_time} to {end_time} ({result.get('deleted_length', end_time - start_time)} beats)"

    @mcp.tool()
    @_tool_handler("duplicating time")
    def duplicate_time(ctx: Context, start_time: float, end_time: float) -> str:
        """Duplicate a section of time in the arrangement (copies and inserts after the selection).

        Parameters:
        - start_time: Start position in beats
        - end_time: End position in beats
        """
        if start_time >= end_time:
            return "Error: start_time must be less than end_time"
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_time", {
            "start_time": start_time,
            "end_time": end_time,
        })
        return f"Duplicated time from {start_time} to {end_time} (pasted at {result.get('pasted_at', end_time)})"

    @mcp.tool()
    @_tool_handler("inserting silence")
    def insert_silence(ctx: Context, position: float, length: float) -> str:
        """Insert silence at a position in the arrangement (shifts everything after).

        Parameters:
        - position: The position in beats to insert silence at
        - length: The length of silence in beats
        """
        if length <= 0:
            return "Error: length must be greater than 0"
        ableton = get_ableton_connection()
        result = ableton.send_command("insert_silence", {
            "position": position,
            "length": length,
        })
        return f"Inserted {length} beats of silence at position {position}"

    @mcp.tool()
    @_tool_handler("creating arrangement MIDI clip")
    def create_arrangement_midi_clip(ctx: Context, track_index: int, time: float, length: float) -> str:
        """Create a new MIDI clip in the arrangement view at a specific time position.

        Requires Live 12.1+ and a MIDI track.

        Parameters:
        - track_index: The index of the MIDI track
        - time: Start time in beats for the new clip
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_arrangement_midi_clip", {
            "track_index": track_index,
            "time": time,
            "length": length,
        })
        return f"Created arrangement MIDI clip on track {track_index} at beat {time}, length {length}"

    @mcp.tool()
    @_tool_handler("creating arrangement audio clip")
    def create_arrangement_audio_clip(ctx: Context, track_index: int, time: float, length: float) -> str:
        """Create a new audio clip in the arrangement view at a specific time position.

        Requires Live 12.2+ and an audio track.

        Parameters:
        - track_index: The index of the audio track
        - time: Start time in beats for the new clip
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_arrangement_audio_clip", {
            "track_index": track_index,
            "time": time,
            "length": length,
        })
        return f"Created arrangement audio clip on track {track_index} at beat {time}, length {length}"

    @mcp.tool()
    @_tool_handler("moving arrangement clip")
    def move_arrangement_clip(ctx: Context, track_index: int,
                                clip_index_in_arrangement: int,
                                new_start_time: float) -> str:
        """Move an arrangement clip to a new start position (Live 12.2+).

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        - new_start_time: New start position in beats
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("move_arrangement_clip", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
            "new_start_time": new_start_time,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("deleting arrangement clip")
    def delete_arrangement_clip(ctx: Context, track_index: int,
                                  clip_index_in_arrangement: int) -> str:
        """Delete an arrangement clip by its index.

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_arrangement_clip", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting arrangement clip properties")
    def set_arrangement_clip_properties(ctx: Context, track_index: int,
                                          clip_index_in_arrangement: int,
                                          muted: Optional[bool] = None,
                                          gain: Optional[float] = None,
                                          name: Optional[str] = None,
                                          color_index: Optional[int] = None,
                                          loop_start: Optional[float] = None,
                                          loop_end: Optional[float] = None,
                                          looping: Optional[bool] = None,
                                          start_marker: Optional[float] = None,
                                          end_marker: Optional[float] = None,
                                          pitch_coarse: Optional[int] = None,
                                          pitch_fine: Optional[int] = None) -> str:
        """Set properties on an arrangement clip (mute, gain, name, color, loop, pitch).

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        - muted: Mute/unmute the clip
        - gain: Audio clip gain
        - name: Clip name
        - color_index: Color index
        - loop_start/loop_end: Loop boundaries
        - looping: Enable/disable looping
        - start_marker/end_marker: Clip markers
        - pitch_coarse: Coarse pitch in semitones
        - pitch_fine: Fine pitch in cents
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        params = {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        }
        for key, val in [("muted", muted), ("gain", gain), ("name", name),
                         ("color_index", color_index), ("loop_start", loop_start),
                         ("loop_end", loop_end), ("looping", looping),
                         ("start_marker", start_marker), ("end_marker", end_marker),
                         ("pitch_coarse", pitch_coarse), ("pitch_fine", pitch_fine)]:
            if val is not None:
                params[key] = val
        ableton = get_ableton_connection()
        result = ableton.send_command("set_arrangement_clip_properties", params)
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting arrangement clip info")
    def get_arrangement_clip_info(ctx: Context, track_index: int,
                                    clip_index_in_arrangement: int) -> str:
        """Get detailed info about a specific arrangement clip.

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_arrangement_clip_info", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting detail clip")
    def set_detail_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """Show a clip in Live's Detail view (the bottom panel).

        Parameters:
        - track_index: The track containing the clip
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_detail_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        name = result.get("clip_name", "?")
        return f"Detail view showing clip '{name}' (track {track_index}, slot {clip_index})"

    @mcp.tool()
    @_tool_handler("selecting scene")
    def select_scene(ctx: Context, scene_index: int) -> str:
        """Select a scene by index in Live's Session view.

        Parameters:
        - scene_index: The index of the scene to select (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("select_scene", {"scene_index": scene_index})
        name = result.get("scene_name", "?")
        return f"Selected scene {scene_index}: '{name}'"
