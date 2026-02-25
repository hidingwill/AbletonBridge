"""Mixer tool handlers for AbletonBridge."""
import json
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_index_allow_negative, _validate_range, _validate_notes


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("setting track arm")
    def set_track_arm(ctx: Context, track_index: int, arm: bool) -> str:
        """
        Set the arm (record enable) state of a track.

        Parameters:
        - track_index: The index of the track
        - arm: True to arm, False to disarm
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_arm", {
            "track_index": track_index,
            "arm": arm
        })
        state = "armed" if result.get('arm', arm) else "disarmed"
        return f"Track {track_index} is now {state}"

    @mcp.tool()
    @_tool_handler("setting track send")
    def set_track_send(ctx: Context, track_index: int, send_index: int, value: float) -> str:
        """
        Set the send level from a track to a return track.

        Parameters:
        - track_index: The index of the source track
        - send_index: The index of the send (0 = Send A, 1 = Send B, etc.)
        - value: The send level (0.0 to 1.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(send_index, "send_index")
        _validate_range(value, "value", 0.0, 1.0)
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_send", {
            "track_index": track_index,
            "send_index": send_index,
            "value": value
        })
        return f"Set track {track_index} send {send_index} to {result.get('value', value)}"

    @mcp.tool()
    @_tool_handler("setting crossfader")
    def set_crossfader(ctx: Context, value: float) -> str:
        """Set the master crossfader position.

        Parameters:
        - value: Crossfader position (0.0=A, 0.5=center, 1.0=B)
        """
        _validate_range(value, "value", 0.0, 1.0)
        ableton = get_ableton_connection()
        result = ableton.send_command("set_crossfader", {"value": value})
        return f"Set crossfader to {result.get('crossfader', value)}"

    @mcp.tool()
    @_tool_handler("getting crossfader")
    def get_crossfader(ctx: Context) -> str:
        """Get the current master crossfader position and range."""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_crossfader", {})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting cue volume")
    def set_cue_volume(ctx: Context, value: float) -> str:
        """Set the cue/preview volume level.

        Parameters:
        - value: Cue volume (0.0 to 1.0, where 0.85 ~ 0dB)
        """
        _validate_range(value, "value", 0.0, 1.0)
        ableton = get_ableton_connection()
        result = ableton.send_command("set_cue_volume", {"value": value})
        return f"Set cue volume to {result.get('cue_volume', value)}"

    @mcp.tool()
    @_tool_handler("setting track delay")
    def set_track_delay(ctx: Context, track_index: int, delay: float) -> str:
        """Set the track delay compensation in milliseconds.

        Parameters:
        - track_index: The index of the track
        - delay: Delay time in ms (negative = earlier, positive = later)
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_track_delay", {
            "track_index": track_index,
            "delay": delay,
        })
        return f"Set track {track_index} delay to {result.get('track_delay', delay)} ms"

    @mcp.tool()
    @_tool_handler("getting track delay")
    def get_track_delay(ctx: Context, track_index: int) -> str:
        """Get the track delay compensation value and range.

        Parameters:
        - track_index: The index of the track
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_track_delay", {"track_index": track_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting panning mode")
    def set_panning_mode(ctx: Context, track_index: int, mode: int) -> str:
        """Set the panning mode for a track.

        Parameters:
        - track_index: The index of the track
        - mode: 0 = Stereo (normal), 1 = Split Stereo (independent L/R)
        """
        _validate_index(track_index, "track_index")
        if mode not in (0, 1):
            raise ValueError("mode must be 0 (Stereo) or 1 (Split Stereo)")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_panning_mode", {
            "track_index": track_index,
            "mode": mode,
        })
        mode_name = "Stereo" if mode == 0 else "Split Stereo"
        return f"Set track {track_index} panning mode to {mode_name}"

    @mcp.tool()
    @_tool_handler("setting split stereo pan")
    def set_split_stereo_pan(ctx: Context, track_index: int,
                              left: float = None, right: float = None) -> str:
        """Set the left and/or right pan values when in Split Stereo panning mode.

        Parameters:
        - track_index: The index of the track
        - left: Left channel pan position (-1.0 to 1.0)
        - right: Right channel pan position (-1.0 to 1.0)
        """
        _validate_index(track_index, "track_index")
        if left is None and right is None:
            raise ValueError("At least one of 'left' or 'right' must be provided")
        params = {"track_index": track_index}
        if left is not None:
            _validate_range(left, "left", -1.0, 1.0)
            params["left"] = left
        if right is not None:
            _validate_range(right, "right", -1.0, 1.0)
            params["right"] = right
        ableton = get_ableton_connection()
        result = ableton.send_command("set_split_stereo_pan", params)
        parts = []
        if "left_split_stereo" in result:
            parts.append(f"left={result['left_split_stereo']}")
        if "right_split_stereo" in result:
            parts.append(f"right={result['right_split_stereo']}")
        return f"Set track {track_index} split stereo pan: {', '.join(parts)}"

    @mcp.tool()
    @_tool_handler("setting crossfade assign")
    def set_crossfade_assign(ctx: Context, track_index: int, assign: int) -> str:
        """Set A/B crossfade assignment for a track.

        Parameters:
        - track_index: The index of the track
        - assign: 0=NONE (no crossfade), 1=A, 2=B
        """
        _validate_index(track_index, "track_index")
        if assign not in (0, 1, 2):
            return "assign must be 0 (NONE), 1 (A), or 2 (B)"
        ableton = get_ableton_connection()
        result = ableton.send_command("set_crossfade_assign", {
            "track_index": track_index,
            "assign": assign,
        })
        name = result.get("track_name", "?")
        label = result.get("crossfade_assign", "?")
        return f"Track '{name}' crossfade set to {label}"

    @mcp.tool()
    @_tool_handler("applying groove")
    def apply_groove(ctx: Context, track_index: int, clip_index: int, groove_amount: float) -> str:
        """Apply groove to a MIDI clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - groove_amount: Groove amount (0.0 to 1.0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("apply_groove", {
            "track_index": track_index,
            "clip_index": clip_index,
            "groove_amount": groove_amount,
        })
        return f"Groove amount set to {result.get('groove_amount', groove_amount)}"

    @mcp.tool()
    @_tool_handler("setting groove settings")
    def set_groove_settings(ctx: Context,
                             groove_amount: float = None,
                             groove_index: int = None,
                             timing_amount: float = None,
                             quantization_amount: float = None,
                             random_amount: float = None,
                             velocity_amount: float = None) -> str:
        """Set global groove amount or individual groove parameters.

        Parameters:
        - groove_amount: Global groove intensity (0.0 to 1.0). Optional.
        - groove_index: Index of the groove to modify (from get_groove_pool). Optional.
        - timing_amount: Groove timing influence (0.0 to 1.0). Requires groove_index.
        - quantization_amount: Groove quantization amount (0.0 to 1.0). Requires groove_index.
        - random_amount: Groove random timing variation (0.0 to 1.0). Requires groove_index.
        - velocity_amount: Groove velocity influence (0.0 to 1.0). Requires groove_index.

        Set groove_amount alone to change the global groove intensity, or specify
        groove_index with one or more individual parameters to modify a specific groove.
        """
        params = {}
        if groove_amount is not None:
            _validate_range(groove_amount, "groove_amount", 0.0, 1.0)
            params["groove_amount"] = groove_amount
        if groove_index is not None:
            _validate_index(groove_index, "groove_index")
            params["groove_index"] = groove_index
        if timing_amount is not None:
            _validate_range(timing_amount, "timing_amount", 0.0, 1.0)
            params["timing_amount"] = timing_amount
        if quantization_amount is not None:
            _validate_range(quantization_amount, "quantization_amount", 0.0, 1.0)
            params["quantization_amount"] = quantization_amount
        if random_amount is not None:
            _validate_range(random_amount, "random_amount", 0.0, 1.0)
            params["random_amount"] = random_amount
        if velocity_amount is not None:
            _validate_range(velocity_amount, "velocity_amount", 0.0, 1.0)
            params["velocity_amount"] = velocity_amount
        if not params:
            return "No parameters specified. Provide groove_amount or groove_index with params."
        ableton = get_ableton_connection()
        result = ableton.send_command("set_groove_settings", params)
        parts = []
        if "groove_amount" in result:
            parts.append(f"Global groove amount: {result['groove_amount']}")
        if "groove_index" in result:
            parts.append(f"Groove {result['groove_index']} ('{result.get('groove_name', '?')}'): "
                         f"timing={result.get('timing_amount', '?')}, "
                         f"quantize={result.get('quantization_amount', '?')}, "
                         f"random={result.get('random_amount', '?')}, "
                         f"velocity={result.get('velocity_amount', '?')}")
        return " | ".join(parts)

    @mcp.tool()
    @_tool_handler("setting mixer parameters")
    def set_mixer(
        ctx: Context,
        track_index: int,
        track_type: str = "track",
        volume: float = None,
        pan: float = None,
        mute: bool = None,
        solo: bool = None,
    ) -> str:
        """Set multiple mixer parameters on any track type in a single call.

        Unified mixer tool that works with regular tracks, return tracks, and master.
        Only provided parameters are changed; omitted ones are left unchanged.

        Parameters:
        - track_index: The index of the track (ignored for master)
        - track_type: "track", "return", or "master"
        - volume: Volume level (0.0 to 1.0, where 0.85 ~ 0dB). Optional.
        - pan: Pan position (-1.0 to 1.0). Optional. Not available for master.
        - mute: Mute state. Optional.
        - solo: Solo state. Optional.
        """
        if volume is None and pan is None and mute is None and solo is None:
            return "No parameters specified. Provide at least one of: volume, pan, mute, solo."

        if track_type not in ("track", "return", "master"):
            raise ValueError("track_type must be 'track', 'return', or 'master'")

        if track_type != "master":
            _validate_index(track_index, "track_index")

        ableton = get_ableton_connection()
        changes = []

        if volume is not None:
            _validate_range(volume, "volume", 0.0, 1.0)
            if track_type == "master":
                ableton.send_command("set_master_volume", {"volume": volume})
            elif track_type == "return":
                ableton.send_command("set_return_track_volume", {
                    "return_track_index": track_index, "volume": volume
                })
            else:
                ableton.send_command("set_track_volume", {
                    "track_index": track_index, "volume": volume
                })
            changes.append(f"volume={volume}")

        if pan is not None:
            _validate_range(pan, "pan", -1.0, 1.0)
            if track_type == "return":
                ableton.send_command("set_return_track_pan", {
                    "return_track_index": track_index, "pan": pan
                })
            elif track_type == "track":
                ableton.send_command("set_track_pan", {
                    "track_index": track_index, "pan": pan
                })
            changes.append(f"pan={pan}")

        if mute is not None:
            if track_type == "return":
                ableton.send_command("set_return_track_mute", {
                    "return_track_index": track_index, "mute": mute
                })
            elif track_type == "track":
                ableton.send_command("set_track_mute", {
                    "track_index": track_index, "mute": mute
                })
            changes.append(f"mute={mute}")

        if solo is not None:
            if track_type == "return":
                ableton.send_command("set_return_track_solo", {
                    "return_track_index": track_index, "solo": solo
                })
            elif track_type == "track":
                ableton.send_command("set_track_solo", {
                    "track_index": track_index, "solo": solo
                })
            changes.append(f"solo={solo}")

        target = f"{track_type} {track_index}" if track_type != "master" else "master"
        return f"Set {target}: {', '.join(changes)}"
