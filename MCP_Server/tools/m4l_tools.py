"""Max for Live (M4L) bridge tool handlers for AbletonBridge."""
import json
import time
from typing import List, Dict, Any
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _m4l_result
from MCP_Server.connections.m4l import get_m4l_connection
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_range


def register_tools(mcp):

    # ==========================================================================
    # M4L Bridge Status & Discovery
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("checking M4L bridge status")
    def m4l_status(ctx: Context) -> str:
        """Check if the AbletonBridge Max for Live bridge device is loaded and responsive.

        The M4L bridge is an optional device that provides access to hidden/non-automatable
        device parameters via the Live Object Model (LOM). All standard MCP tools work
        without it; only the hidden-parameter tools require it.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("ping")
        data = _m4l_result(result)
        version = data.get("version", "unknown")
        return f"M4L bridge connected (v{version})."


    @mcp.tool()
    @_tool_handler("discovering device parameters")
    def discover_device_params(ctx: Context, track_index: int, device_index: int) -> str:
        """Discover ALL parameters for a device including hidden/non-automatable ones.

        Use to LIST parameter indices and names -- needed before calling set_device_hidden_parameter
        or batch_set_hidden_parameters. To READ current parameter values instead, use
        get_device_hidden_parameters.

        Uses the M4L bridge to enumerate every parameter exposed by the Live Object Model,
        which typically includes parameters not visible through the standard Remote Script API.
        Works with any Ableton device (Operator, Wavetable, Simpler, Analog, Drift, etc.).

        Requires the AbletonBridge M4L device to be loaded on any track.

        Compare the results with get_device_parameters() to see which parameters are hidden.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")

        m4l = get_m4l_connection()
        result = m4l.send_command("discover_params", {
            "track_index": track_index,
            "device_index": device_index
        })

        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("getting hidden device parameters")
    def get_device_hidden_parameters(ctx: Context, track_index: int, device_index: int) -> str:
        """Get ALL parameters for a device including hidden/non-automatable ones.

        Use to READ current parameter values (including hidden ones). To get parameter
        indices for setting values, use discover_device_params instead.

        This is similar to get_device_parameters() but uses the M4L bridge to access
        the full Live Object Model parameter tree, which exposes parameters that the
        standard API hides. Works with any Ableton device.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")

        m4l = get_m4l_connection()
        result = m4l.send_command("get_hidden_params", {
            "track_index": track_index,
            "device_index": device_index
        })

        data = _m4l_result(result)
        device_name = data.get("device_name", "Unknown")
        device_class = data.get("device_class", "Unknown")
        params = data.get("parameters", [])

        output = f"Device: {device_name} ({device_class})\n"
        output += f"Total LOM parameters: {len(params)}\n\n"

        for p in params:
            quant = " [quantized]" if p.get("is_quantized") else ""
            output += (
                f"  [{p.get('index', '?')}] {p.get('name', '?')}: "
                f"{p.get('value', '?')} "
                f"(range: {p.get('min', '?')} \u2013 {p.get('max', '?')}){quant}\n"
            )
            if p.get("value_items"):
                output += f"       options: {p.get('value_items')}\n"

        return output


    @mcp.tool()
    @_tool_handler("setting hidden device parameter")
    def set_device_hidden_parameter(
        ctx: Context,
        track_index: int,
        device_index: int,
        parameter_index: int,
        value: float
    ) -> str:
        """Set a device parameter by its LOM index, including hidden/non-automatable ones.

        Only for hidden/non-automatable params not accessible via the standard
        set_device_parameter. Use discover_device_params() first to find parameter indices.
        The value will be clamped to the parameter's valid range.
        Works with any Ableton device.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(parameter_index, "parameter_index")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("value must be a number.")

        m4l = get_m4l_connection()
        result = m4l.send_command("set_hidden_param", {
            "track_index": track_index,
            "device_index": device_index,
            "parameter_index": parameter_index,
            "value": value
        })

        data = _m4l_result(result)
        name = data.get("parameter_name", "Unknown")
        actual = data.get("actual_value", "?")
        clamped = data.get("was_clamped", False)
        msg = f"Set parameter [{parameter_index}] '{name}' to {actual}"
        if clamped:
            msg += f" (clamped from requested {value})"
        return msg


    @mcp.tool()
    @_tool_handler("batch setting parameters")
    def batch_set_hidden_parameters(
        ctx: Context,
        track_index: int,
        device_index: int,
        parameters: List[Dict[str, float]]
    ) -> str:
        """Set multiple device parameters at once by their LOM indices (including hidden ones).

        Only for hidden/non-automatable params. For standard visible params, use
        set_device_parameters instead. Much faster than calling
        set_device_hidden_parameter() in a loop -- single round-trip to the M4L bridge.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device on the track
        - parameters: List of {"index": parameter_index, "value": target_value} dicts

        Use discover_device_params() first to find parameter indices.
        Values will be clamped to each parameter's valid range.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        if not isinstance(parameters, list) or len(parameters) == 0:
            raise ValueError("parameters must be a non-empty list.")

        # Filter out parameter index 0 ("Device On") to prevent accidentally
        # disabling the device -- a common source of issues.
        safe_params = [p for p in parameters if "index" in p and int(p["index"]) != 0]
        skipped = len(parameters) - len(safe_params)

        for i, p in enumerate(safe_params):
            if not isinstance(p, dict):
                raise ValueError(f"Parameter at index {i} must be a dictionary.")
            if "index" not in p or "value" not in p:
                raise ValueError(f"Parameter at index {i} must have 'index' and 'value' keys.")

        if len(safe_params) == 0:
            return "No settable parameters after filtering (parameter 0 'Device On' is excluded)."

        # Send individual set_hidden_param commands with a small delay between
        # each to avoid overwhelming Ableton.  This is more reliable than the
        # base64-encoded batch OSC approach which can fail with long payloads.
        m4l = get_m4l_connection()
        ok_count = 0
        fail_count = 0
        errors = []

        for p in safe_params:
            try:
                result = m4l.send_command("set_hidden_param", {
                    "track_index": track_index,
                    "device_index": device_index,
                    "parameter_index": int(p["index"]),
                    "value": float(p["value"])
                })
                if result.get("status") == "success":
                    ok_count += 1
                else:
                    fail_count += 1
                    errors.append(f"[{p['index']}]: {result.get('message', '?')}")
            except Exception as e:
                fail_count += 1
                errors.append(f"[{p['index']}]: {str(e)}")

            # Small delay between params to let Ableton breathe
            if len(safe_params) > 6:
                time.sleep(0.05)

        total = ok_count + fail_count
        msg = f"Batch set complete: {ok_count}/{total} parameters set successfully ({fail_count} failed)."
        if skipped:
            msg += f" ({skipped} skipped: 'Device On' excluded for safety.)"
        if errors:
            msg += f" Errors: {'; '.join(errors[:5])}"
        return msg


    # ==========================================================================
    # Automation States
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting automation states")
    def get_automation_states(ctx: Context, track_index: int, device_index: int) -> str:
        """Get automation state for all parameters of a device via M4L bridge.

        Returns only parameters that have automation (state > 0).
        States: 0=none, 1=active, 2=overridden (manually changed after automation was written).

        Use this to check which parameters have automation before modifying them,
        or to detect overridden automation that may need re-enabling.

        Requires the AbletonBridge M4L device to be loaded on any track.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device to inspect
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_automation_states", {
            "track_index": track_index,
            "device_index": device_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Chain Discovery & Parameters
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("discovering device chains via M4L")
    def discover_chains_m4l(ctx: Context, track_index: int, device_index: int, extra_path: str = "") -> str:
        """Discover chains in a rack device via M4L bridge with enhanced detail.

        Returns chain hierarchy including:
        - Regular chains with their devices
        - Return chains (Rack-level sends, e.g. Instrument Rack return chains)
        - Drum pad details: in_note, out_note, choke_group, mute, solo

        Use extra_path to navigate nested racks (e.g. "chains 0 devices 1").

        Requires the AbletonBridge M4L device to be loaded on any track.

        Parameters:
        - track_index: The index of the track containing the rack device
        - device_index: The index of the rack device
        - extra_path: Additional LOM path to navigate into nested racks (optional)
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("discover_chains", {
            "track_index": track_index,
            "device_index": device_index,
            "extra_path": extra_path,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("getting chain device parameters via M4L")
    def get_chain_device_params_m4l(ctx: Context, track_index: int, device_index: int, chain_index: int, chain_device_index: int) -> str:
        """Discover ALL parameters (including hidden/non-automatable) of a device inside a rack chain.

        Uses M4L bridge to access the full LOM parameter tree of a device nested
        inside a chain of a rack (Instrument Rack, Audio Effect Rack, Drum Rack, etc.).

        Requires the AbletonBridge M4L device to be loaded on any track.

        Parameters:
        - track_index: The index of the track containing the rack
        - device_index: The index of the rack device
        - chain_index: The index of the chain within the rack
        - chain_device_index: The index of the device within the chain
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        _validate_index(chain_device_index, "chain_device_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_chain_device_params", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
            "chain_device_index": chain_device_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("setting chain device parameter via M4L")
    def set_chain_device_param_m4l(ctx: Context, track_index: int, device_index: int, chain_index: int, chain_device_index: int, parameter_index: int, value: float) -> str:
        """Set a parameter value on a device inside a rack chain via M4L bridge.

        Allows setting any parameter (including hidden/non-automatable) on devices
        nested inside rack chains. Use get_chain_device_params_m4l() first to discover
        available parameters and their valid ranges.

        Requires the AbletonBridge M4L device to be loaded on any track.

        Parameters:
        - track_index: The index of the track containing the rack
        - device_index: The index of the rack device
        - chain_index: The index of the chain within the rack
        - chain_device_index: The index of the device within the chain
        - parameter_index: The index of the parameter to set
        - value: The value to set the parameter to (must be within min/max range)
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        _validate_index(chain_device_index, "chain_device_index")
        _validate_index(parameter_index, "parameter_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("set_chain_device_param", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
            "chain_device_index": chain_device_index,
            "parameter_index": parameter_index,
            "value": value,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Note Surgery (M4L Bridge v3.6.0)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting clip notes with IDs")
    def get_clip_notes_with_ids(ctx: Context, track_index: int, clip_index: int) -> str:
        """Get all MIDI notes in a clip with stable note IDs via M4L bridge.

        Returns notes with unique note_id fields that can be used for in-place
        editing via modify_clip_notes() or surgical removal via remove_clip_notes_by_id().
        Each note includes: note_id, pitch, start_time, duration, velocity, mute,
        probability, velocity_deviation, release_velocity.

        Requires the AbletonBridge M4L device. Live 11+ required for note IDs.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the MIDI clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_clip_notes_by_id", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("modifying clip notes by ID")
    def modify_clip_notes(ctx: Context, track_index: int, clip_index: int, modifications: str) -> str:
        """Modify MIDI notes in-place by their stable note ID via M4L bridge.

        Performs non-destructive in-place editing -- no remove+re-add needed.
        Use get_clip_notes_with_ids() first to get note IDs.

        Each modification dict must include 'note_id' and any properties to change:
        pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity.

        Requires the AbletonBridge M4L device. Live 11+ required.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the MIDI clip
        - modifications: JSON string of list of note modification dicts, each with 'note_id' and changed properties.
          Example: '[{"note_id": 1, "velocity": 100}, {"note_id": 5, "pitch": 64, "start_time": 2.0}]'
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        mods = json.loads(modifications) if isinstance(modifications, str) else modifications
        m4l = get_m4l_connection()
        result = m4l.send_command("modify_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "modifications": mods,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("removing clip notes by ID")
    def remove_clip_notes_by_id(ctx: Context, track_index: int, clip_index: int, note_ids: str) -> str:
        """Remove specific MIDI notes by their stable note ID via M4L bridge.

        Surgical note removal -- only removes the exact notes specified by ID.
        Use get_clip_notes_with_ids() first to get note IDs.

        Requires the AbletonBridge M4L device. Live 11+ required.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot containing the MIDI clip
        - note_ids: JSON string of list of note IDs to remove. Example: '[1, 5, 12]'
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ids = json.loads(note_ids) if isinstance(note_ids, str) else note_ids
        m4l = get_m4l_connection()
        result = m4l.send_command("remove_clip_notes_by_id", {
            "track_index": track_index,
            "clip_index": clip_index,
            "note_ids": ids,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Chain Mixing
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting chain mixing state")
    def get_chain_mixing(ctx: Context, track_index: int, device_index: int, chain_index: int) -> str:
        """Get mixing state (volume, pan, sends, mute, solo) of a chain in a rack device via M4L bridge.

        Returns the ChainMixerDevice properties: volume, panning, chain_activator (mute),
        sends, plus the chain's mute and solo state. Critical for Drum Rack pad balancing
        and Instrument Rack chain mixing.

        Requires the AbletonBridge M4L device.

        Parameters:
        - track_index: The index of the track containing the rack
        - device_index: The index of the rack device (Instrument Rack, Audio Effect Rack, Drum Rack)
        - chain_index: The index of the chain within the rack
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_chain_mixing", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("setting chain mixing state")
    def set_chain_mixing(ctx: Context, track_index: int, device_index: int, chain_index: int, properties: str) -> str:
        """Set mixing properties on a chain in a rack device via M4L bridge.

        Set any combination of: volume, panning, chain_activator (1=active, 0=muted),
        mute (0/1), solo (0/1), sends (array of {index, value}).

        Requires the AbletonBridge M4L device.

        Parameters:
        - track_index: The index of the track containing the rack
        - device_index: The index of the rack device
        - chain_index: The index of the chain within the rack
        - properties: JSON string with mixing properties to set.
          Example: '{"volume": 0.8, "panning": -0.5, "mute": 0, "sends": [{"index": 0, "value": 0.5}]}'
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        props = json.loads(properties) if isinstance(properties, str) else properties
        m4l = get_m4l_connection()
        result = m4l.send_command("set_chain_mixing", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
            "properties": props,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # AB Compare
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("comparing device AB presets")
    def device_ab_compare(ctx: Context, track_index: int, device_index: int, action: str) -> str:
        """Compare device presets using AB comparison via M4L bridge (Live 12.3+).

        Save device state to A/B slots for instant comparison during sound design.
        Actions:
        - 'get_state': Check if AB comparison is supported and which slot is active
        - 'save': Save current device state to the other AB slot
        - 'toggle': Toggle between A and B presets

        Requires the AbletonBridge M4L device and Ableton Live 12.3+.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device
        - action: 'get_state', 'save', or 'toggle'
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        if action not in ("get_state", "save", "toggle"):
            return "action must be 'get_state', 'save', or 'toggle'"
        m4l = get_m4l_connection()
        result = m4l.send_command("device_ab_compare", {
            "track_index": track_index,
            "device_index": device_index,
            "action": action,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Clip Scrub (M4L version)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("scrubbing clip")
    def clip_scrub(ctx: Context, track_index: int, clip_index: int, action: str, beat_time: float = 0.0) -> str:
        """Scrub within a clip at a specific beat position via M4L bridge.

        Performs quantized clip scrubbing (like mouse scrubbing in Ableton) --
        respects Global Quantization, loops in time with transport.
        Different from navigate_playback(scrub_by) which moves the global transport.

        Actions:
        - 'scrub': Start scrubbing at the given beat_time (continues until stop_scrub)
        - 'stop_scrub': Stop scrubbing

        Requires the AbletonBridge M4L device.

        Parameters:
        - track_index: The index of the track containing the clip
        - clip_index: The index of the clip slot
        - action: 'scrub' or 'stop_scrub'
        - beat_time: The beat position to scrub to (only for 'scrub' action)
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        if action not in ("scrub", "stop_scrub"):
            return "action must be 'scrub' or 'stop_scrub'"
        m4l = get_m4l_connection()
        result = m4l.send_command("clip_scrub", {
            "track_index": track_index,
            "clip_index": clip_index,
            "action": action,
            "beat_time": beat_time,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Split Stereo (M4L versions)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting split stereo panning")
    def get_split_stereo(ctx: Context, track_index: int) -> str:
        """Get the split stereo panning values (left and right) for a track via M4L bridge.

        Returns the Left Split Stereo and Right Split Stereo DeviceParameter values
        from the track's mixer_device. These control independent L/R panning when
        split stereo mode is enabled.

        Requires the AbletonBridge M4L device.

        Parameters:
        - track_index: The index of the track
        """
        _validate_index(track_index, "track_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_split_stereo", {
            "track_index": track_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("setting split stereo panning")
    def set_split_stereo(ctx: Context, track_index: int, left: float, right: float) -> str:
        """Set the split stereo panning values (left and right) for a track via M4L bridge.

        Sets the Left Split Stereo and Right Split Stereo DeviceParameter values
        on the track's mixer_device.

        Requires the AbletonBridge M4L device.

        Parameters:
        - track_index: The index of the track
        - left: Left channel pan value (typically -1.0 to 1.0)
        - right: Right channel pan value (typically -1.0 to 1.0)
        """
        _validate_index(track_index, "track_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("set_split_stereo", {
            "track_index": track_index,
            "left": left,
            "right": right,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    # ==========================================================================
    # Event-Driven Monitoring (M4L Bridge)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("starting observation")
    def observe_property(ctx: Context, lom_path: str, property_name: str) -> str:
        """Start monitoring a Live Object Model property for changes.

        Uses M4L's live.observer for near-instant (~10ms) change detection,
        much faster than polling via TCP.

        Parameters:
        - lom_path: The LOM path to observe (e.g., "live_set", "live_set tracks 0")
        - property_name: The property to watch (e.g., "is_playing", "tempo", "current_song_time")

        Common useful observations:
        - "live_set" + "is_playing" -- detect play/stop
        - "live_set" + "tempo" -- detect tempo changes
        - "live_set" + "current_song_time" -- track playback position
        - "live_set tracks N" + "output_meter_level" -- track level meter

        Use get_property_changes() to retrieve accumulated changes.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("observe_property", {
            "lom_path": lom_path,
            "property_name": property_name,
        })

        data = _m4l_result(result)
        if data.get("already_observing"):
            return f"Already observing {data.get('key', '?')}."
        return f"Now observing: {data.get('path', '?')}.{data.get('property', '?')}"


    @mcp.tool()
    @_tool_handler("stopping observation")
    def stop_observing(ctx: Context, lom_path: str, property_name: str) -> str:
        """Stop monitoring a Live Object Model property.

        Parameters:
        - lom_path: The LOM path that was being observed
        - property_name: The property that was being watched

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("stop_observing", {
            "lom_path": lom_path,
            "property_name": property_name,
        })

        data = _m4l_result(result)
        if not data.get("was_observing", True):
            return f"Was not observing {data.get('key', '?')}."
        return (
            f"Stopped observing {data.get('key', '?')}. "
            f"Discarded {data.get('pending_changes_discarded', 0)} pending changes."
        )


    @mcp.tool()
    @_tool_handler("getting property changes")
    def get_property_changes(ctx: Context) -> str:
        """Get accumulated property change events from all active observers.

        Returns all changes since the last call (changes are cleared after reading).
        Each change includes the property name, new value, and timestamp.

        Use observe_property() first to start monitoring properties.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("get_observed_changes")

        data = _m4l_result(result)
        total = data.get("total_changes", 0)
        obs_count = data.get("observer_count", 0)
        changes = data.get("changes", {})

        if obs_count == 0:
            return "No active observers. Use observe_property() to start monitoring."

        if total == 0:
            return f"No changes detected ({obs_count} active observers)."

        output = f"Property Changes ({total} total, {obs_count} observers):\n\n"
        for key, events in changes.items():
            output += f"  {key}:\n"
            for evt in events[-20:]:  # Show last 20 per observer
                output += f"    [{evt.get('time', '?')}] {evt.get('property', '?')} = {evt.get('value', '?')}\n"
            if len(events) > 20:
                output += f"    ... ({len(events) - 20} more)\n"
        return output


    # ==========================================================================
    # Undo-Clean Parameter Control (M4L Bridge)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("setting parameter cleanly")
    def set_parameter_clean(
        ctx: Context,
        track_index: int,
        device_index: int,
        parameter_index: int,
        value: float,
    ) -> str:
        """Set a device parameter via the M4L bridge with minimal undo impact.

        Unlike set_device_parameter (which goes through the Remote Script and creates
        a full undo entry), this routes through the M4L bridge for a lighter touch.
        Useful for automation-style continuous parameter changes where you don't want
        to pollute the undo history.

        Parameters:
        - track_index: The track containing the device
        - device_index: The device index on the track
        - parameter_index: The LOM parameter index (use discover_device_params to find indices)
        - value: The value to set (will be clamped to parameter min/max)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(parameter_index, "parameter_index")

        m4l = get_m4l_connection()
        result = m4l.send_command("set_param_clean", {
            "track_index": track_index,
            "device_index": device_index,
            "parameter_index": parameter_index,
            "value": float(value),
        })

        data = _m4l_result(result)
        output = (
            f"Parameter '{data.get('parameter_name', '?')}' "
            f"set to {data.get('actual_value', '?')}"
        )
        if data.get("was_clamped"):
            output += f" (clamped from {data.get('requested_value', '?')})"
        return output


    # ==========================================================================
    # Audio Analysis (M4L Bridge)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("analyzing audio")
    def analyze_track_audio(ctx: Context, track_index: int = -1) -> str:
        """Analyze audio levels on any track (cross-track meter reading).

        Returns output meter levels (left/right) from the LOM for the target track,
        plus MSP-derived RMS/peak data if the Max patch has audio analysis objects
        connected (MSP data always comes from the device's own track).

        Parameters:
            track_index: Track to analyze (0-based). Default -1 = the track where
                         the M4L bridge device is loaded. Use -2 for master track.
                         Any track index 0+ reads that track's meters remotely.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("analyze_audio", {"track_index": track_index})
        data = _m4l_result(result)
        target = data.get("target_track_index", -1)
        track_label = data.get("track_name", f"track {target}")
        if target == -2:
            track_label = data.get("track_name", "Master")
        output = f"Audio Analysis ({track_label}):\n"

        if "output_meter_left" in data:
            output += f"  Output Meter L: {data['output_meter_left']:.4f}\n"
        if "output_meter_right" in data:
            output += f"  Output Meter R: {data['output_meter_right']:.4f}\n"
        if "output_meter_peak_left" in data:
            output += f"  Peak Level: {data['output_meter_peak_left']:.4f}\n"

        if data.get("has_msp_data"):
            output += f"\n  MSP Analysis from device track (age: {data.get('msp_data_age_ms', '?')}ms):\n"
            output += f"    RMS L: {data.get('rms_left', 0):.4f}  R: {data.get('rms_right', 0):.4f}\n"
            output += f"    Peak L: {data.get('peak_left', 0):.4f}  R: {data.get('peak_right', 0):.4f}\n"
        else:
            note = data.get("note", "")
            if note:
                output += f"\n  Note: {note}\n"

        return output


    @mcp.tool()
    @_tool_handler("analyzing spectrum")
    def analyze_track_spectrum(ctx: Context) -> str:
        """Get spectral analysis data from the track where the M4L Audio Effect bridge is loaded.

        Returns frequency band magnitudes (8-band via fffb~ filter bank), dominant band,
        and spectral centroid. The M4L device must be an Audio Effect (not MIDI Effect)
        with plugin~ -> fffb~ 8 -> snapshot~ -> pack -> prepend spectrum_data -> [js] wired.

        If no spectral data is available, returns instructions for setting up the analysis.

        Requires the AbletonBridge M4L Audio Effect device to be loaded on a track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("analyze_spectrum")
        data = _m4l_result(result)

        if not data.get("has_spectrum"):
            return data.get("note", "No spectral data available. Set up fft~ in the Max patch.")

        output = "Spectral Analysis:\n"
        output += f"  Bins: {data.get('bin_count', 0)}\n"
        output += f"  Dominant bin: {data.get('dominant_bin', '?')} (magnitude: {data.get('dominant_magnitude', 0):.4f})\n"
        output += f"  Spectral centroid: {data.get('spectral_centroid', 0):.2f}\n"
        output += f"  Data age: {data.get('data_age_ms', '?')}ms\n"

        return output


    @mcp.tool()
    @_tool_handler("in cross-track audio analysis")
    def analyze_cross_track_audio(ctx: Context, track_index: int, wait_ms: int = 500) -> str:
        """Analyze real MSP audio data (RMS, peak, 8-band spectrum) from ANY track via send-based routing.

        Temporarily routes audio from the target track to the return track where the
        M4L bridge device is loaded. Non-destructive: source track's main output to
        master continues normally, and the send level is restored after capture.

        Requirements:
        - The AbletonBridge M4L Audio Effect device must be on a RETURN track
        - Audio must be playing on the target track during analysis
        - The Max patch must have plugin~ -> fffb~ 8 -> abs~ -> snapshot~ -> [js] wired
          (abs~ after each fffb~ outlet is REQUIRED for correct amplitude values)
        - The Max patch must have plugin~ -> peakamp~ -> snapshot~ -> [js] for RMS/peak

        Parameters:
            track_index: Track to analyze (0-based index of regular tracks)
            wait_ms: How long to wait for audio to flow through MSP chain (default 500ms,
                     range 300-2000ms). Increase for more stable readings.

        Returns RMS levels, peak levels, 8-band spectrum, spectral centroid, and output
        meters for both source and analysis return tracks.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("analyze_cross_track", {
            "track_index": track_index,
            "wait_ms": wait_ms,
        })

        data = _m4l_result(result)
        track_name = data.get("track_name", f"Track {track_index}")
        output = f"Cross-Track Audio Analysis ({track_name}, track {track_index}):\n"
        output += f"  Return track used: {data.get('return_track_index', '?')}\n"
        output += f"  Capture wait: {data.get('capture_wait_ms', '?')}ms "
        output += f"(actual: {data.get('actual_capture_time_ms', '?')}ms)\n\n"

        if data.get("has_msp_data"):
            output += "  MSP Analysis (from return track DSP chain):\n"
            output += f"    RMS  L: {data.get('rms_left', 0):.6f}  R: {data.get('rms_right', 0):.6f}\n"
            output += f"    Peak L: {data.get('peak_left', 0):.6f}  R: {data.get('peak_right', 0):.6f}\n"
        else:
            note = data.get("note", "No MSP data captured.")
            output += f"  MSP Data: NOT AVAILABLE\n  Note: {note}\n"

        output += f"\n  Source Track Meters:\n"
        output += f"    L: {data.get('source_output_meter_left', 0):.4f}  "
        output += f"R: {data.get('source_output_meter_right', 0):.4f}\n"
        output += f"  Return Track Meters:\n"
        output += f"    L: {data.get('return_output_meter_left', 0):.4f}  "
        output += f"R: {data.get('return_output_meter_right', 0):.4f}\n"

        if data.get("has_spectrum"):
            output += f"\n  Spectrum ({data.get('bin_count', 0)} bands):\n"
            bins = data.get("spectrum", [])
            band_labels = ["Sub", "Bass", "Low-Mid", "Mid", "Upper-Mid", "Presence", "Brilliance", "Air"]
            for i, val in enumerate(bins):
                label = band_labels[i] if i < len(band_labels) else f"Band {i}"
                bar = "#" * min(40, int(val * 50))
                output += f"    {label:>12}: {val:.4f} {bar}\n"
            output += f"  Dominant band: {data.get('dominant_bin', '?')} "
            output += f"(magnitude: {data.get('dominant_magnitude', 0):.4f})\n"
            output += f"  Spectral centroid: {data.get('spectral_centroid', 0):.2f}\n"

        output += f"\n  Send restored to: {data.get('original_send_value', 0):.4f}\n"
        return output


    # ==========================================================================
    # App Version
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting Ableton version")
    def get_ableton_version(ctx: Context) -> str:
        """Get the Ableton Live application version via M4L bridge.

        Returns major, minor, bugfix version numbers and display string.
        Useful for version-gating features (e.g. AB comparison requires Live 12.3+).

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("get_app_version")
        data = _m4l_result(result)
        display = data.get("display", "Unknown")
        vs = data.get("version_string")
        if vs:
            return f"{display} ({vs})"
        return display


    # ==========================================================================
    # Rack Chain Operations (M4L)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("inserting rack chain via M4L")
    def rack_insert_chain_m4l(ctx: Context, track_index: int, device_index: int,
                               chain_index: int = 0) -> str:
        """Insert a new chain into a Rack device via Max for Live LOM.

        This uses the M4L bridge for deeper LOM access (Live 12.3+).

        Parameters:
        - track_index: The index of the track
        - device_index: The index of the Rack device
        - chain_index: Position to insert the chain (default: 0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("rack_insert_chain", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
        })
        data = _m4l_result(result)
        return f"Inserted chain at index {chain_index} (total chains: {data.get('chain_count', '?')})"


    @mcp.tool()
    @_tool_handler("inserting device into chain via M4L")
    def chain_insert_device_m4l(ctx: Context, track_index: int, device_index: int,
                                  chain_index: int, device_uri: str,
                                  target_index: int = 0) -> str:
        """Insert a device into a chain of a Rack device via Max for Live LOM.

        Parameters:
        - track_index: The index of the track
        - device_index: The index of the Rack device
        - chain_index: The index of the chain
        - device_uri: The browser URI of the device to insert
        - target_index: Position in the chain to insert at (default: 0)
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        _validate_index(target_index, "target_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("chain_insert_device_m4l", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
            "device_uri": device_uri,
            "target_index": target_index,
        })
        data = _m4l_result(result)
        return f"Inserted device '{device_uri}' into chain {chain_index}"


    @mcp.tool()
    @_tool_handler("setting drum chain note")
    def set_drum_chain_note(ctx: Context, track_index: int, device_index: int,
                             chain_index: int, note: int) -> str:
        """Set the input note (pad assignment) for a Drum Rack chain via M4L (Live 12.3+).

        Parameters:
        - track_index: The index of the track
        - device_index: The index of the Drum Rack device
        - chain_index: The index of the drum chain/pad
        - note: The MIDI note number to assign (0-127)
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(chain_index, "chain_index")
        _validate_range(note, "note", 0, 127)
        m4l = get_m4l_connection()
        result = m4l.send_command("set_drum_chain_note", {
            "track_index": track_index,
            "device_index": device_index,
            "chain_index": chain_index,
            "note": int(note),
        })
        data = _m4l_result(result)
        return f"Set drum chain {chain_index} input note to {data.get('in_note', note)}"


    # ==========================================================================
    # Take Lanes
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting take lanes via M4L")
    def get_take_lanes_m4l(ctx: Context, track_index: int) -> str:
        """Get take lane information for a track via Max for Live LOM.

        Returns take lane names, active status, and count.

        Parameters:
        - track_index: The index of the track
        """
        _validate_index(track_index, "track_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("get_take_lanes", {
            "track_index": track_index,
        })
        data = _m4l_result(result)
        return json.dumps(data)


    @mcp.tool()
    @_tool_handler("getting take lanes")
    def get_take_lanes(ctx: Context, track_index: int) -> str:
        """Get take lanes for a track. Take lanes are used for comping in Arrangement View --
        record multiple takes and pick the best parts.

        Parameters:
        - track_index: Track to get take lanes for
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_take_lanes", {"track_index": track_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("creating take lane")
    def create_take_lane(ctx: Context, track_index: int) -> str:
        """Create a new take lane for a track. Used for comping workflows in Arrangement View.

        Parameters:
        - track_index: Track to create the take lane on
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("create_take_lane", {"track_index": track_index})
        return f"Take lane created on track {track_index} (now {result.get('take_lane_count', '?')} lanes)"


    # ==========================================================================
    # Rack Variations
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("storing rack variation")
    def rack_store_variation(ctx: Context, track_index: int, device_index: int) -> str:
        """Store the current Rack macro state as a new variation via M4L.

        Parameters:
        - track_index: The index of the track
        - device_index: The index of the Rack device
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("rack_store_variation", {
            "track_index": track_index,
            "device_index": device_index,
        })
        data = _m4l_result(result)
        return "Stored new rack variation"


    @mcp.tool()
    @_tool_handler("recalling rack variation")
    def rack_recall_variation(ctx: Context, track_index: int, device_index: int,
                               variation_index: int) -> str:
        """Recall a stored Rack macro variation by index via M4L.

        Parameters:
        - track_index: The index of the track
        - device_index: The index of the Rack device
        - variation_index: The index of the variation to recall
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        _validate_index(variation_index, "variation_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("rack_recall_variation", {
            "track_index": track_index,
            "device_index": device_index,
            "variation_index": variation_index,
        })
        data = _m4l_result(result)
        return f"Recalled rack variation {variation_index}"


    # ==========================================================================
    # Arrangement Clip Creation (M4L)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("creating arrangement MIDI clip via M4L")
    def create_arrangement_midi_clip_m4l(ctx: Context, track_index: int,
                                           time: float, length: float) -> str:
        """Create a MIDI clip in the arrangement via Max for Live LOM.

        Alternative to the TCP-based create_arrangement_midi_clip.

        Parameters:
        - track_index: The index of the MIDI track
        - time: Start time in beats
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        m4l = get_m4l_connection()
        result = m4l.send_command("create_arrangement_midi_clip_m4l", {
            "track_index": track_index,
            "time": float(time),
            "length": float(length),
        })
        data = _m4l_result(result)
        return f"Created arrangement MIDI clip on track {track_index} at beat {time}"


    @mcp.tool()
    @_tool_handler("creating arrangement audio clip via M4L")
    def create_arrangement_audio_clip_m4l(ctx: Context, track_index: int,
                                            time: float, length: float) -> str:
        """Create an audio clip in the arrangement via Max for Live LOM.

        Alternative to the TCP-based create_arrangement_audio_clip.

        Parameters:
        - track_index: The index of the audio track
        - time: Start time in beats
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        m4l = get_m4l_connection()
        result = m4l.send_command("create_arrangement_audio_clip_m4l", {
            "track_index": track_index,
            "time": float(time),
            "length": float(length),
        })
        data = _m4l_result(result)
        return f"Created arrangement audio clip on track {track_index} at beat {time}"


    # ==========================================================================
    # Cue Points & Locators (M4L Bridge)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting cue points")
    def get_cue_points(ctx: Context) -> str:
        """Get all cue points (locators) from the arrangement view.

        Returns a list of all arrangement locators with their names and positions (in beats).
        Cue points are the markers visible in the arrangement timeline.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("get_cue_points")
        data = _m4l_result(result)
        cue_points = data.get("cue_points", [])
        count = data.get("cue_point_count", 0)

        if count == 0:
            return "No cue points (locators) found in the arrangement."

        output = f"Cue Points ({count}):\n\n"
        for cp in cue_points:
            time_beats = cp.get("time", 0)
            bars = int(time_beats // 4) + 1
            beat_in_bar = (time_beats % 4) + 1
            output += (
                f"  [{cp.get('index', '?')}] \"{cp.get('name', '')}\" "
                f"at {time_beats:.2f} beats (bar {bars}, beat {beat_in_bar:.1f})\n"
            )
        return output


    @mcp.tool()
    @_tool_handler("jumping to cue point")
    def jump_to_cue_point(ctx: Context, cue_point_index: int) -> str:
        """Jump the playback position to a specific cue point (locator).

        Parameters:
        - cue_point_index: The index of the cue point to jump to (use get_cue_points to see available indices)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(cue_point_index, "cue_point_index")
        m4l = get_m4l_connection()
        result = m4l.send_command("jump_to_cue_point", {
            "cue_point_index": cue_point_index
        })

        data = _m4l_result(result)
        return (
            f"Jumped to cue point [{data.get('jumped_to', '?')}] "
            f"\"{data.get('name', '')}\" at {data.get('time', 0):.2f} beats."
        )


    # ==========================================================================
    # Groove Pool Access (M4L Bridge)
    # ==========================================================================

    @mcp.tool()
    @_tool_handler("getting groove pool")
    def get_groove_pool(ctx: Context) -> str:
        """Get all grooves from Ableton's groove pool.

        Returns groove templates with their properties: base amount, timing, velocity,
        random, and quantize rate. Grooves affect the rhythmic feel of clips.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        m4l = get_m4l_connection()
        result = m4l.send_command("get_groove_pool")
        data = _m4l_result(result)
        grooves = data.get("grooves", [])
        count = data.get("groove_count", 0)

        if count == 0:
            return "Groove pool is empty. Drag groove files into Ableton's groove pool to use them."

        output = f"Groove Pool ({count} grooves):\n\n"
        for g in grooves:
            output += f"  [{g.get('index', '?')}] \"{g.get('name', '')}\"\n"
            if "base" in g:
                output += f"    Base: {g['base']:.0%}"
            if "timing" in g:
                output += f"  Timing: {g['timing']:.0%}"
            if "velocity" in g:
                output += f"  Velocity: {g['velocity']:.0%}"
            if "random" in g:
                output += f"  Random: {g['random']:.0%}"
            if "quantize_rate" in g:
                output += f"  Quantize: {g['quantize_rate']}"
            output += "\n"
        return output


    @mcp.tool()
    @_tool_handler("setting groove properties")
    def set_groove_properties(
        ctx: Context,
        groove_index: int,
        base: float = None,
        timing: float = None,
        velocity: float = None,
        random: float = None,
        quantize_rate: int = None,
    ) -> str:
        """Set properties on a groove in the groove pool.

        Parameters:
        - groove_index: The index of the groove (use get_groove_pool to see available indices)
        - base: Base groove amount (0.0 to 1.0)
        - timing: Timing groove amount (0.0 to 1.0)
        - velocity: Velocity groove amount (0.0 to 1.0)
        - random: Random groove amount (0.0 to 1.0)
        - quantize_rate: Quantize rate index

        All property parameters are optional -- only provided values will be changed.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(groove_index, "groove_index")
        properties = {}
        if base is not None:
            properties["base"] = float(base)
        if timing is not None:
            properties["timing"] = float(timing)
        if velocity is not None:
            properties["velocity"] = float(velocity)
        if random is not None:
            properties["random"] = float(random)
        if quantize_rate is not None:
            properties["quantize_rate"] = int(quantize_rate)

        if not properties:
            return "No properties specified to set. Provide at least one of: base, timing, velocity, random, quantize_rate."

        m4l = get_m4l_connection()
        result = m4l.send_command("set_groove_properties", {
            "groove_index": groove_index,
            "properties": properties,
        })

        data = _m4l_result(result)
        set_count = data.get("properties_set", 0)
        details = data.get("details", [])
        errors = data.get("errors", [])
        output = f"Groove [{groove_index}]: {set_count} properties set."
        if details:
            output += "\n" + ", ".join(f"{d['property']}={d['value']}" for d in details)
        if errors:
            output += f"\nErrors: {errors}"
        return output
