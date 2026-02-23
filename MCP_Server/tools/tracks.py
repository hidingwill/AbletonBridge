"""Track management tool handlers for AbletonBridge."""
import json
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _m4l_result
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.connections.m4l import get_m4l_connection
from MCP_Server.validation import _validate_index, _validate_index_allow_negative, _validate_range
import MCP_Server.state as state


def register_tools(mcp):
    """Register track management tools with the MCP server."""

    @mcp.tool()
    @_tool_handler("getting track info")
    def get_track_info(ctx: Context, track_index: int) -> str:
        """
        Get detailed information about a specific track in Ableton.

        Parameters:
        - track_index: The index of the track to get information about
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_info", {"track_index": track_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting all tracks info")
    def get_all_tracks_info(ctx: Context) -> str:
        """Get information about all tracks in the session at once (bulk query)."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_all_tracks_info")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting return tracks info")
    def get_return_tracks_info(ctx: Context) -> str:
        """Get detailed information about all return tracks (bulk query)."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_return_tracks_info")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("creating MIDI track")
    def create_midi_track(ctx: Context, index: int = -1) -> str:
        """
        Create a new MIDI track in the Ableton session.

        Parameters:
        - index: The index to insert the track at (-1 = end of list)
        """
        _validate_index_allow_negative(index, "index", min_value=-1)
        ableton = get_ableton_connection()
        result = ableton.send_command("create_midi_track", {"index": index})
        return f"Created new MIDI track: {result.get('name', 'unknown')}"

    @mcp.tool()
    @_tool_handler("creating audio track")
    def create_audio_track(ctx: Context, index: int = -1) -> str:
        """
        Create a new audio track in the Ableton session.

        Parameters:
        - index: The index to insert the track at (-1 = end of list)
        """
        _validate_index_allow_negative(index, "index", min_value=-1)
        ableton = get_ableton_connection()
        result = ableton.send_command("create_audio_track", {"index": index})
        return f"Created new audio track: {result.get('name', 'unknown')}"

    @mcp.tool()
    @_tool_handler("deleting track")
    def delete_track(ctx: Context, track_index: int) -> str:
        """
        Delete a track from the session.

        Parameters:
        - track_index: The index of the track to delete
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_track", {"track_index": track_index})
        return f"Deleted track '{result.get('track_name', 'unknown')}' at index {track_index}"

    @mcp.tool()
    @_tool_handler("duplicating track")
    def duplicate_track(ctx: Context, track_index: int) -> str:
        """
        Duplicate a track with all its devices and clips.

        Parameters:
        - track_index: The index of the track to duplicate
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_track", {"track_index": track_index})
        return f"Duplicated track '{result.get('source_name', 'unknown')}' to new track '{result.get('new_name', 'unknown')}' at index {result.get('new_index', 'unknown')}"

    @mcp.tool()
    @_tool_handler("setting track name")
    def set_track_name(ctx: Context, track_index: int, name: str) -> str:
        """
        Set the name of a track.

        Parameters:
        - track_index: The index of the track to rename
        - name: The new name for the track
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_name", {"track_index": track_index, "name": name})
        return f"Renamed track to: {result.get('name', name)}"

    @mcp.tool()
    @_tool_handler("setting track color")
    def set_track_color(ctx: Context, track_index: int, color_index: int) -> str:
        """Set the color of a track.

        Parameters:
        - track_index: The index of the track
        - color_index: The color index (0-69, Ableton's color palette)
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_color", {
            "track_index": track_index,
            "color_index": color_index,
        })
        return f"Track {track_index} color set to {color_index}"

    @mcp.tool()
    @_tool_handler("arming track")
    def arm_track(ctx: Context, track_index: int) -> str:
        """Arm a track for recording.

        Parameters:
        - track_index: The index of the track to arm
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("arm_track", {"track_index": track_index})
        return f"Track {track_index} armed"

    @mcp.tool()
    @_tool_handler("disarming track")
    def disarm_track(ctx: Context, track_index: int) -> str:
        """Disarm a track (disable recording).

        Parameters:
        - track_index: The index of the track to disarm
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("disarm_track", {"track_index": track_index})
        return f"Track {track_index} disarmed"

    @mcp.tool()
    @_tool_handler("grouping tracks")
    def group_tracks(ctx: Context, track_indices: list) -> str:
        """Group multiple tracks together.

        Parameters:
        - track_indices: List of track indices to group together
        """
        if not isinstance(track_indices, list) or len(track_indices) < 2:
            return "Error: track_indices must be a list of at least 2 track indices"
        ableton = get_ableton_connection()
        result = ableton.send_command("group_tracks", {"track_indices": track_indices})
        return f"Grouped {len(track_indices)} tracks"

    @mcp.tool()
    @_tool_handler("creating return track")
    def create_return_track(ctx: Context) -> str:
        """Create a new return track in the session."""
        ableton = get_ableton_connection()
        result = ableton.send_command("create_return_track")
        return f"Created return track: {result.get('name', 'unknown')}"

    @mcp.tool()
    @_tool_handler("deleting return track")
    def delete_return_track(ctx: Context, return_index: int) -> str:
        """Delete a return track.

        Parameters:
        - return_index: The index of the return track to delete
        """
        _validate_index(return_index, "return_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_return_track", {"return_index": return_index})
        return f"Deleted return track {return_index}"

    @mcp.tool()
    @_tool_handler("getting return tracks")
    def get_return_tracks(ctx: Context) -> str:
        """Get information about all return tracks."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_return_tracks")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting return track info")
    def get_return_track_info(ctx: Context, return_track_index: int) -> str:
        """
        Get detailed information about a specific return track.

        Parameters:
        - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
        """
        _validate_index(return_track_index, "return_track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_return_track_info", {
            "return_track_index": return_track_index
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting master track info")
    def get_master_track_info(ctx: Context) -> str:
        """Get detailed information about the master track, including volume, panning, and devices."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_master_track_info")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("freezing track")
    def freeze_track(ctx: Context, track_index: int) -> str:
        """Freeze a track (render effects in place to reduce CPU load).

        Parameters:
        - track_index: The index of the track to freeze
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("freeze_track", {"track_index": track_index})
        return f"Track {track_index} ({result.get('track_name', '?')}) frozen"

    @mcp.tool()
    @_tool_handler("unfreezing track")
    def unfreeze_track(ctx: Context, track_index: int) -> str:
        """Unfreeze a track.

        Parameters:
        - track_index: The index of the track to unfreeze
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("unfreeze_track", {"track_index": track_index})
        return f"Track {track_index} ({result.get('track_name', '?')}) unfrozen"

    @mcp.tool()
    @_tool_handler("setting track fold")
    def set_track_fold(ctx: Context, track_index: int, fold_state: bool) -> str:
        """Collapse or expand a group track.

        Parameters:
        - track_index: The index of the group track
        - fold_state: True to collapse (fold), False to expand (unfold)
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_fold", {
            "track_index": track_index,
            "fold_state": fold_state,
        })
        name = result.get("track_name", "?")
        state = "collapsed" if fold_state else "expanded"
        return f"Track '{name}' {state}"

    @mcp.tool()
    @_tool_handler("setting track collapse")
    def set_track_collapse(ctx: Context, track_index: int, collapsed: bool) -> str:
        """Collapse or expand a track in the arrangement/session view.

        Parameters:
        - track_index: The index of the track
        - collapsed: True to collapse, False to expand
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_collapse", {
            "track_index": track_index,
            "collapsed": collapsed,
        })
        state = "collapsed" if result.get("collapsed", collapsed) else "expanded"
        return f"Track {track_index} is now {state}"

    @mcp.tool()
    @_tool_handler("getting track routing")
    def get_track_routing(ctx: Context, track_index: int) -> str:
        """Get current input/output routing and available options for a track.

        Parameters:
        - track_index: The index of the track

        Returns the current input/output routing types and channels, plus lists
        of all available routing options. Useful for understanding and configuring
        side-chain routing, resampling, and multi-output setups.
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_routing", {
            "track_index": track_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting track routing")
    def set_track_routing(ctx: Context, track_index: int,
                          input_type: str = None, input_channel: str = None,
                          output_type: str = None, output_channel: str = None) -> str:
        """Set input/output routing for a track by display name.

        Parameters:
        - track_index: The index of the track
        - input_type: Input routing type (e.g. 'Ext. In', 'No Input', a track name). Optional.
        - input_channel: Input channel (e.g. '1/2', 'All Channels', 'Pre FX'). Optional.
        - output_type: Output routing type (e.g. 'Master', 'Sends Only', a track name). Optional.
        - output_channel: Output channel (e.g. 'Track In'). Optional.

        Use get_track_routing first to see available routing options for the track.
        Useful for setting up side-chain compression, resampling, or routing to
        specific outputs.
        """
        _validate_index(track_index, "track_index")
        params = {"track_index": track_index}
        if input_type is not None:
            params["input_type"] = input_type
        if input_channel is not None:
            params["input_channel"] = input_channel
        if output_type is not None:
            params["output_type"] = output_type
        if output_channel is not None:
            params["output_channel"] = output_channel
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_routing", params)
        changes = [f"{k}={v}" for k, v in result.items() if k not in ("track_index", "track_name")]
        return f"Track {track_index} ('{result.get('track_name', '?')}') routing updated: {', '.join(changes) if changes else 'no changes'}"

    @mcp.tool()
    @_tool_handler("setting track monitoring")
    def set_track_monitoring(ctx: Context, track_index: int, state: int) -> str:
        """Set the monitoring state of a track.

        Parameters:
        - track_index: The index of the track
        - state: 0=IN (always monitor input), 1=AUTO (monitor when armed), 2=OFF (never monitor)

        Controls whether the track passes its input through to the output.
        AUTO is the default and monitors only when the track is armed for recording.
        """
        _validate_index(track_index, "track_index")
        _validate_range(state, "state", 0, 2)
        state_names = {0: "IN", 1: "AUTO", 2: "OFF"}
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_monitoring", {
            "track_index": track_index,
            "state": state,
        })
        state_name = state_names.get(result.get("monitoring_state", state), "unknown")
        return f"Track {track_index} ('{result.get('track_name', '?')}') monitoring set to {state_name}"

    @mcp.tool()
    @_tool_handler("getting track meters")
    def get_track_meters(ctx: Context, track_index: int = None) -> str:
        """Get live output meter levels and currently playing/fired clip slot info.

        Parameters:
        - track_index: Optional. If provided, returns data for just that track. If omitted, returns all tracks.

        Returns output_meter_left/right (0.0-1.0), playing_slot_index (-1 if none),
        and fired_slot_index (-1 if none).
        """
        params = {}
        if track_index is not None:
            _validate_index(track_index, "track_index")
            params["track_index"] = track_index
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_meters", params)
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting track data")
    def get_track_data(ctx: Context, track_index: int, key: str) -> str:
        """Get persistent data stored on a track (survives save/load).

        Parameters:
        - track_index: The track index
        - key: The data key to retrieve
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_data", {
            "track_index": track_index, "key": key,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting track data")
    def set_track_data(ctx: Context, track_index: int, key: str, value: str) -> str:
        """Store persistent data on a track (survives save/load in .als file).

        Parameters:
        - track_index: The track index
        - key: The data key to store
        - value: The string value to store
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_data", {
            "track_index": track_index, "key": key, "value": value,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("selecting track")
    def select_track(ctx: Context, track_index: int, track_type: str = "track") -> str:
        """Select a track in Live's Session or Arrangement view.

        Parameters:
        - track_index: The index of the track to select (0-based). Ignored for master.
        - track_type: 'track' (default), 'return', or 'master'
        """
        if track_type not in ("track", "return", "master"):
            return "track_type must be 'track', 'return', or 'master'"
        if track_type != "master":
            _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("select_track", {
            "track_index": track_index,
            "track_type": track_type,
        })
        name = result.get("selected_track", "?")
        return f"Selected {track_type} track: '{name}'"

    # NOTE: select_device_in_view, get_selected_parameter, select_instrument
    # are registered in tools/devices.py (their canonical home)
