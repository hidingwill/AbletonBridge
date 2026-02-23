"""Audio analysis tool handlers for AbletonBridge."""
import json
from typing import Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index


def register_tools(mcp):

    @mcp.tool()
    @_tool_handler("getting audio clip info")
    def get_audio_clip_info(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get detailed information about an audio clip (warp mode, gain, file path, etc.).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_audio_clip_info", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("analyzing audio clip")
    def analyze_audio_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """Analyze an audio clip comprehensively (tempo, warp, sample properties, frequency hints).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("analyze_audio_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        return json.dumps(result)

    # NOTE: get_track_meters is registered in tools/tracks.py (its canonical home)

    @mcp.tool()
    @_tool_handler("getting track input meters")
    def get_track_input_meters(ctx: Context, track_index: Optional[int] = None) -> str:
        """Get input meter levels for one or all tracks.

        Parameters:
        - track_index: Track index (omit for all tracks)
        """
        ableton = get_ableton_connection()
        params = {}
        if track_index is not None:
            _validate_index(track_index, "track_index")
            params["track_index"] = track_index
        result = ableton.send_command("get_track_input_meters", params)
        return json.dumps(result)
