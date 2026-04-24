"""Scene management tool handlers for AbletonBridge."""
import json
from typing import Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("creating scene")
    def create_scene(ctx: Context, index: int = -1, name: str = "") -> str:
        """Create a new scene in the session.

        Parameters:
        - index: Position to insert the scene (-1 = end)
        - name: Optional name for the new scene
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("create_scene", {"index": index, "name": name})
        scene_name = result.get("name", "")
        scene_idx = result.get("index", index)
        label = f" '{scene_name}'" if scene_name else ""
        return f"Created scene{label} at index {scene_idx}"

    @mcp.tool()
    @_tool_handler("deleting scene")
    def delete_scene(ctx: Context, scene_index: int) -> str:
        """Delete a scene from the session.

        Parameters:
        - scene_index: The index of the scene to delete (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_scene", {"scene_index": scene_index})
        name = result.get("scene_name", "")
        return f"Deleted scene {scene_index}: '{name}'"

    @mcp.tool()
    @_tool_handler("duplicating scene")
    def duplicate_scene(ctx: Context, scene_index: int) -> str:
        """Duplicate a scene (inserts copy below the original).

        Parameters:
        - scene_index: The index of the scene to duplicate (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_scene", {"scene_index": scene_index})
        new_idx = result.get("new_index", scene_index + 1)
        name = result.get("name", "")
        return f"Duplicated scene {scene_index} → new scene {new_idx}: '{name}'"

    @mcp.tool()
    @_tool_handler("firing scene")
    def fire_scene(ctx: Context, scene_index: int) -> str:
        """Fire (launch) a scene — triggers all clips in that scene row.

        Parameters:
        - scene_index: The index of the scene to fire (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        ableton.send_command("fire_scene", {"scene_index": scene_index})
        return f"Fired scene {scene_index}"

    @mcp.tool()
    @_tool_handler("firing scene as selected")
    def fire_scene_as_selected(ctx: Context, scene_index: int) -> str:
        """Fire a scene without moving the selection highlight.

        Parameters:
        - scene_index: The index of the scene to fire (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        ableton.send_command("fire_scene_as_selected", {"scene_index": scene_index})
        return f"Fired scene {scene_index} (selection unchanged)"

    @mcp.tool()
    @_tool_handler("setting scene name")
    def set_scene_name(ctx: Context, scene_index: int, name: str) -> str:
        """Set the name of a scene.

        Parameters:
        - scene_index: The index of the scene (0-based)
        - name: The new name for the scene
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        ableton.send_command("set_scene_name", {"scene_index": scene_index, "name": name})
        return f"Set scene {scene_index} name to '{name}'"

    @mcp.tool()
    @_tool_handler("setting scene color")
    def set_scene_color(ctx: Context, scene_index: int, color_index: int) -> str:
        """Set the color of a scene.

        Parameters:
        - scene_index: The index of the scene (0-based)
        - color_index: Color index (0-69)
        """
        _validate_index(scene_index, "scene_index")
        if color_index < 0 or color_index > 69:
            raise ValueError("color_index must be 0-69")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_scene_color", {
            "scene_index": scene_index,
            "color_index": color_index,
        })
        return f"Set scene {scene_index} color to index {result.get('color_index', color_index)}"

    @mcp.tool()
    @_tool_handler("setting scene tempo")
    def set_scene_tempo(ctx: Context, scene_index: int, tempo: float) -> str:
        """Set or clear a scene's tempo override.

        When a scene has a tempo set, launching it changes the song tempo.
        Set tempo to 0 to clear the override.

        Parameters:
        - scene_index: The index of the scene (0-based)
        - tempo: BPM value (20-999), or 0 to clear the override
        """
        _validate_index(scene_index, "scene_index")
        if tempo != 0 and (tempo < 20 or tempo > 999):
            raise ValueError("Tempo must be 0 (clear) or 20-999 BPM")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_scene_tempo", {
            "scene_index": scene_index,
            "tempo": tempo,
        })
        if tempo == 0:
            return f"Cleared tempo override for scene {scene_index}"
        return f"Set scene {scene_index} tempo to {result.get('tempo', tempo)} BPM"

    @mcp.tool()
    @_tool_handler("getting scene follow actions")
    def get_scene_follow_actions(ctx: Context, scene_index: int) -> str:
        """Get follow action settings for a scene.

        Returns follow_action_0, follow_action_1, probability, time, enabled, linked.

        Parameters:
        - scene_index: The index of the scene (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_scene_follow_actions", {"scene_index": scene_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting scene follow actions")
    def set_scene_follow_actions(
        ctx: Context,
        scene_index: int,
        follow_action_0: Optional[int] = None,
        follow_action_1: Optional[int] = None,
        follow_action_probability: Optional[float] = None,
        follow_action_time: Optional[float] = None,
        follow_action_enabled: Optional[bool] = None,
        follow_action_linked: Optional[bool] = None,
    ) -> str:
        """Set follow action settings for a scene.

        Follow actions determine what happens after a scene finishes playing.

        Parameters:
        - scene_index: The index of the scene (0-based)
        - follow_action_0: First follow action type (int enum)
        - follow_action_1: Second follow action type (int enum)
        - follow_action_probability: Probability of action_0 vs action_1 (0.0-1.0)
        - follow_action_time: Time before follow action triggers (in beats)
        - follow_action_enabled: Enable/disable follow actions
        - follow_action_linked: Link follow action time to clip length
        """
        _validate_index(scene_index, "scene_index")
        params = {"scene_index": scene_index}
        for key, val in [
            ("follow_action_0", follow_action_0),
            ("follow_action_1", follow_action_1),
            ("follow_action_probability", follow_action_probability),
            ("follow_action_time", follow_action_time),
            ("follow_action_enabled", follow_action_enabled),
            ("follow_action_linked", follow_action_linked),
        ]:
            if val is not None:
                params[key] = val
        if len(params) == 1:
            raise ValueError("At least one follow action parameter must be specified")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_scene_follow_actions", params)
        changed = [k for k in result if k not in ("scene_index", "scene_name")]
        return f"Updated scene {scene_index} follow actions: {', '.join(changed)}"
