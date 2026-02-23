"""Grid notation tool handlers for AbletonBridge."""
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index


def register_tools(mcp):

    @mcp.tool()
    @_tool_handler("converting clip to grid")
    def clip_to_grid(ctx: Context, track_index: int, clip_index: int) -> str:
        """Read a MIDI clip and display as ASCII grid notation (auto-detects drum vs melodic).

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        try:
            from MCP_Server.grid_notation import notes_to_grid
            _validate_index(track_index, "track_index")
            _validate_index(clip_index, "clip_index")
            ableton = get_ableton_connection()
            result = ableton.send_command("get_clip_notes", {
                "track_index": track_index,
                "clip_index": clip_index,
                "start_time": 0.0,
                "time_span": 0.0,
                "start_pitch": 0,
                "pitch_span": 128,
            })
            notes = result.get("notes", [])
            clip_length = result.get("clip_length", 4.0)
            clip_name = result.get("clip_name", "Unknown")
            grid = notes_to_grid(notes)
            return f"Clip: {clip_name} ({clip_length} beats)\n\n{grid}"
        except ImportError:
            return "Error: grid_notation module not available"

    @mcp.tool()
    @_tool_handler("writing grid to clip")
    def grid_to_clip(
        ctx: Context,
        track_index: int,
        clip_index: int,
        grid: str,
        length: float = 4.0,
        clear_existing: bool = True,
    ) -> str:
        """Write ASCII grid notation to a MIDI clip. Creates the clip if it doesn't exist.

        Grid format for drums:
            KK|o---o---|o---o-o-|
            SN|----o---|----o---|
            HC|x-x-x-x-|x-x-x-x-|

        Grid format for melodic:
            G4|----o---|--------|
            E4|--o-----|oooo----|
            C4|o-------|----oooo|

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot
        - grid: ASCII grid string (multi-line)
        - length: Clip length in beats (default: 4.0)
        - clear_existing: Clear existing notes before writing (default: true)
        """
        from MCP_Server.grid_notation import parse_grid
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if length <= 0:
            return "Error: length must be greater than 0"

        notes = parse_grid(grid)
        if not notes:
            return "Error: No notes parsed from grid. Check the grid format."

        ableton = get_ableton_connection()

        # Create clip if it doesn't exist (ignore error if it already exists)
        try:
            ableton.send_command("create_clip", {
                "track_index": track_index,
                "clip_index": clip_index,
                "length": length,
            })
        except Exception:
            pass

        # Clear existing notes if requested
        if clear_existing:
            try:
                ableton.send_command("clear_clip_notes", {
                    "track_index": track_index,
                    "clip_index": clip_index,
                })
            except Exception:
                pass

        # Add the parsed notes
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })
        return f"Wrote {len(notes)} notes from grid to track {track_index}, slot {clip_index} ({length} beats)"
