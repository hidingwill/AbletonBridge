"""Automation tool handlers for AbletonBridge."""
import json
import math
from typing import List, Dict, Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_range, _validate_automation_points, _reduce_automation_points


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("creating clip automation")
    def create_clip_automation(ctx: Context, track_index: int, clip_index: int,
                                parameter_name: str, automation_points: List[Dict[str, float]]) -> str:
        """Create automation for a parameter within a session clip.

        For automation inside a session clip's envelope. For arrangement-level track
        automation (Volume, Pan, etc. on the timeline), use create_track_automation instead.

        Parameters:
        - track_index: The index of the track
        - clip_index: The index of the clip slot
        - parameter_name: Name of the parameter to automate (e.g., "Osc 1 Pos", "Filter 1 Freq")
        - automation_points: List of {time: float, value: float} dictionaries

        IMPORTANT — use as FEW points as possible.  Ableton linearly interpolates
        between breakpoints, so a smooth ramp from 0→1 over 4 beats needs only
        2 points:  [{"time": 0, "value": 0}, {"time": 4, "value": 1}]
        For a triangle (up then down) use 3 points.  For gentle curves 4-8 max.
        Do NOT send 20+ points for simple shapes — it creates staircase artifacts.

        Values are in the parameter's native range (usually 0.0–1.0).
        Time is in beats from clip start.
        Any existing automation for this parameter is cleared before writing.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_automation_points(automation_points)
        automation_points = _reduce_automation_points(automation_points)
        ableton = get_ableton_connection()
        result = ableton.send_command("create_clip_automation", {
            "track_index": track_index,
            "clip_index": clip_index,
            "parameter_name": parameter_name,
            "automation_points": automation_points
        })
        pts = result.get("points_added", len(automation_points))
        return f"Created automation with {pts} points for parameter '{parameter_name}'"

    @mcp.tool()
    @_tool_handler("getting clip automation")
    def get_clip_automation(ctx: Context, track_index: int, clip_index: int,
                            parameter_name: str) -> str:
        """
        Read existing automation from a clip for a specific parameter.

        Samples the automation envelope at 64 evenly-spaced points across the clip length.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - parameter_name: Name of the parameter (e.g., "Volume", "Pan", or any device parameter name)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_automation", {
            "track_index": track_index,
            "clip_index": clip_index,
            "parameter_name": parameter_name,
        })
        if not result.get("has_automation"):
            reason = result.get("reason", "No automation found")
            return f"No automation for '{parameter_name}': {reason}"
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("clearing clip automation")
    def clear_clip_automation(ctx: Context, track_index: int, clip_index: int,
                              parameter_name: str) -> str:
        """
        Clear automation for a specific parameter in a clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        - parameter_name: Name of the parameter to clear automation for
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_clip_automation", {
            "track_index": track_index,
            "clip_index": clip_index,
            "parameter_name": parameter_name,
        })
        if result.get("cleared"):
            return f"Cleared automation for '{parameter_name}'"
        return f"Could not clear automation for '{parameter_name}': {result.get('reason', 'Unknown')}"

    @mcp.tool()
    @_tool_handler("listing automated parameters")
    def list_clip_automated_parameters(ctx: Context, track_index: int, clip_index: int) -> str:
        """
        List all parameters that have automation in a given clip.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("list_clip_automated_params", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        params = result.get("automated_parameters", [])
        if not params:
            return "No automated parameters found in this clip"
        output = f"Found {len(params)} automated parameter(s):\n\n"
        for p in params:
            source = p.get("source", "Unknown")
            output += f"• {p.get('name', '?')} (source: {source})"
            if "device_index" in p:
                output += f" [device {p['device_index']}]"
            output += "\n"
        return output

    @mcp.tool()
    @_tool_handler("creating track automation")
    def create_track_automation(
        ctx: Context,
        track_index: int,
        parameter_name: str,
        automation_points: list,
    ) -> str:
        """Create automation for a track parameter (arrangement-level).

        For arrangement-level automation on the timeline. For automation within a
        session clip's envelope, use create_clip_automation instead.

        Parameters:
        - track_index: The index of the track
        - parameter_name: Name of the parameter to automate (e.g., "Volume", "Pan")
        - automation_points: List of {time: float, value: float} dictionaries
        """
        _validate_index(track_index, "track_index")
        _validate_automation_points(automation_points)
        automation_points = _reduce_automation_points(automation_points)
        ableton = get_ableton_connection()
        result = ableton.send_command("create_track_automation", {
            "track_index": track_index,
            "parameter_name": parameter_name,
            "automation_points": automation_points,
        })
        return f"Created track automation for '{parameter_name}' with {result.get('points_added', len(automation_points))} points"

    @mcp.tool()
    @_tool_handler("clearing track automation")
    def clear_track_automation(
        ctx: Context,
        track_index: int,
        parameter_name: str,
        start_time: float,
        end_time: float,
    ) -> str:
        """Clear automation for a parameter in a time range (arrangement-level).

        Parameters:
        - track_index: The index of the track
        - parameter_name: Name of the parameter to clear automation for
        - start_time: Start time in beats
        - end_time: End time in beats
        """
        _validate_index(track_index, "track_index")
        if start_time >= end_time:
            return "Error: start_time must be less than end_time"
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_track_automation", {
            "track_index": track_index,
            "parameter_name": parameter_name,
            "start_time": start_time,
            "end_time": end_time,
        })
        return f"Cleared automation for '{parameter_name}' from {start_time} to {end_time}"

    @mcp.tool()
    @_tool_handler("creating automation curve")
    def create_automation_curve(ctx: Context, track_index: int, clip_index: int,
                                  parameter_name: str, curve_type: str = "sine",
                                  start_value: float = 0.0, end_value: float = 1.0,
                                  cycles: float = 1.0, points: int = 32) -> str:
        """Generate curved automation for a clip parameter.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - parameter_name: Name of the parameter to automate
        - curve_type: "sine", "cosine", "exponential", "logarithmic", "linear", "triangle", "sawtooth", "s_curve", "ease_in", "ease_out", "ease_in_out", "square", "pulse", "random" (default: "sine")
        - start_value: Starting value (0.0-1.0, default: 0.0)
        - end_value: Ending value (0.0-1.0, default: 1.0)
        - cycles: Number of cycles for periodic curves (default: 1.0)
        - points: Number of automation points to generate (default: 32)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")

        # Get clip length
        ableton = get_ableton_connection()
        clip_info = ableton.send_command("get_clip_info", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        clip_length = clip_info.get("length", 4.0)

        automation_points = []
        for i in range(points):
            t = i / max(1, points - 1)  # normalized 0..1
            time = t * clip_length

            if curve_type == "linear":
                value = start_value + (end_value - start_value) * t
            elif curve_type == "sine":
                value = start_value + (end_value - start_value) * (0.5 + 0.5 * math.sin(2 * math.pi * cycles * t - math.pi / 2))
            elif curve_type == "cosine":
                value = start_value + (end_value - start_value) * (0.5 - 0.5 * math.cos(2 * math.pi * cycles * t))
            elif curve_type == "exponential":
                value = start_value + (end_value - start_value) * (t ** 2)
            elif curve_type == "logarithmic":
                value = start_value + (end_value - start_value) * math.sqrt(t)
            elif curve_type == "triangle":
                phase = (t * cycles) % 1.0
                tri = 2 * phase if phase < 0.5 else 2 * (1 - phase)
                value = start_value + (end_value - start_value) * tri
            elif curve_type == "sawtooth":
                phase = (t * cycles) % 1.0
                value = start_value + (end_value - start_value) * phase
            elif curve_type == "s_curve":
                # Smooth S-curve (sigmoid-like via cubic Hermite)
                s = t * t * (3 - 2 * t)
                value = start_value + (end_value - start_value) * s
            elif curve_type == "ease_in":
                # Slow start, fast end (cubic)
                value = start_value + (end_value - start_value) * (t ** 3)
            elif curve_type == "ease_out":
                # Fast start, slow end (cubic)
                value = start_value + (end_value - start_value) * (1 - (1 - t) ** 3)
            elif curve_type == "ease_in_out":
                # Slow start and end, fast middle (quintic)
                s = t * t * t * (t * (t * 6 - 15) + 10)
                value = start_value + (end_value - start_value) * s
            elif curve_type == "square":
                # Square wave
                phase = (t * cycles) % 1.0
                value = end_value if phase < 0.5 else start_value
            elif curve_type == "pulse":
                # Pulse wave (25% duty cycle)
                phase = (t * cycles) % 1.0
                value = end_value if phase < 0.25 else start_value
            elif curve_type == "random":
                import random
                value = start_value + (end_value - start_value) * random.random()
            else:
                raise ValueError(f"Unknown curve_type '{curve_type}'")

            value = max(0.0, min(1.0, value))
            automation_points.append({"time": time, "value": value})

        ableton.send_command("create_clip_automation", {
            "track_index": track_index,
            "clip_index": clip_index,
            "parameter_name": parameter_name,
            "automation_points": automation_points,
        })

        return f"Created {curve_type} automation curve ({points} points) for '{parameter_name}' on track {track_index} clip {clip_index}"

    @mcp.tool()
    @_tool_handler("clearing clip envelope")
    def clear_clip_envelope(ctx: Context, track_index: int, clip_index: int,
                             parameter_name: str) -> str:
        """Clear automation envelope for a specific parameter using clip.clear_envelope().

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - parameter_name: Name of the parameter whose envelope to clear
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_clip_envelope", {
            "track_index": track_index, "clip_index": clip_index,
            "parameter_name": parameter_name,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("clearing all clip envelopes")
    def clear_all_clip_envelopes(ctx: Context, track_index: int, clip_index: int) -> str:
        """Clear ALL automation envelopes from a clip.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("clear_all_clip_envelopes", {
            "track_index": track_index, "clip_index": clip_index,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting automation value at time")
    def get_clip_automation_value(ctx: Context, track_index: int, clip_index: int,
                                    parameter_name: str, time: float) -> str:
        """Read the automation envelope value at a specific time.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - parameter_name: Name of the parameter
        - time: Time position in beats to read the value at
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_automation_value", {
            "track_index": track_index, "clip_index": clip_index,
            "parameter_name": parameter_name, "time": time,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting hi-res automation")
    def get_clip_automation_hires(ctx: Context, track_index: int, clip_index: int,
                                    parameter_name: str, sample_count: int = 128) -> str:
        """Read automation envelope with configurable sample resolution.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - parameter_name: Name of the parameter
        - sample_count: Number of sample points (2-512, default: 128)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_automation_hires", {
            "track_index": track_index, "clip_index": clip_index,
            "parameter_name": parameter_name, "sample_count": sample_count,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("creating step automation")
    def create_step_automation(ctx: Context, track_index: int, clip_index: int,
                                 parameter_name: str, steps: list) -> str:
        """Create step (held-value) automation — each step holds its value for a duration.

        Parameters:
        - track_index: The track index
        - clip_index: The clip slot index
        - parameter_name: Name of the parameter to automate
        - steps: List of {time, value, duration} dicts. duration > 0 creates a held step.
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_step_automation", {
            "track_index": track_index, "clip_index": clip_index,
            "parameter_name": parameter_name, "steps": steps,
        })
        return json.dumps(result)
