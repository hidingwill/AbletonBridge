"""Snapshot, macro, and parameter-map tool handlers for AbletonBridge."""
import json
import time
import uuid
import logging
from typing import Dict, Any, List
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _m4l_result
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.connections.m4l import get_m4l_connection
from MCP_Server.validation import _validate_index, _validate_range
from MCP_Server.tools.devices import _m4l_batch_set_params
import MCP_Server.state as state

logger = logging.getLogger("AbletonBridge")


def register_tools(mcp):

    # ==================================================================
    # Snapshot tools
    # ==================================================================

    @mcp.tool()
    @_tool_handler("capturing device snapshot")
    def snapshot_device_state(
        ctx: Context,
        track_index: int,
        device_index: int,
        snapshot_name: str = ""
    ) -> str:
        """Capture the complete state of a device (all parameters including hidden ones).

        Stores the snapshot in memory with a unique ID for later recall.
        Use restore_device_snapshot() to restore a saved state.
        Use list_snapshots() to see all stored snapshots.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device on the track
        - snapshot_name: Optional human-readable name for the snapshot

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")

        m4l = get_m4l_connection()
        result = m4l.send_command("discover_params", {
            "track_index": track_index,
            "device_index": device_index
        })

        if result.get("status") != "success":
            return f"M4L bridge error: {result.get('message', 'Unknown error')}"

        data = result.get("result", {})
        snapshot_id = str(uuid.uuid4())[:8]
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        snapshot = {
            "id": snapshot_id,
            "name": snapshot_name or f"{data.get('device_name', 'Unknown')}_{snapshot_id}",
            "timestamp": timestamp,
            "track_index": track_index,
            "device_index": device_index,
            "device_name": data.get("device_name", "Unknown"),
            "device_class": data.get("device_class", "Unknown"),
            "parameter_count": data.get("parameter_count", 0),
            "parameters": data.get("parameters", [])
        }

        with state.store_lock:
            state.snapshot_store[snapshot_id] = snapshot

        return (
            f"Snapshot saved: '{snapshot['name']}' (ID: {snapshot_id})\n"
            f"Device: {snapshot['device_name']} ({snapshot['device_class']})\n"
            f"Parameters captured: {snapshot['parameter_count']}\n"
            f"Timestamp: {timestamp}"
        )

    @mcp.tool()
    @_tool_handler("restoring device snapshot")
    def restore_device_snapshot(
        ctx: Context,
        snapshot_id: str,
        track_index: int = -1,
        device_index: int = -1
    ) -> str:
        """Restore a previously captured device state from a snapshot.

        Applies all parameter values from the snapshot to the device using batch set.
        By default restores to the same track/device the snapshot was taken from.
        Optionally specify different track_index/device_index to apply to a different device.

        Parameters:
        - snapshot_id: The ID of the snapshot to restore (from snapshot_device_state or list_snapshots)
        - track_index: Override target track (-1 = use original track from snapshot)
        - device_index: Override target device (-1 = use original device from snapshot)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        try:
            with state.store_lock:
                if snapshot_id not in state.snapshot_store:
                    return f"Snapshot '{snapshot_id}' not found. Use list_snapshots() to see available snapshots."
                snapshot = state.snapshot_store[snapshot_id]

            target_track = track_index if track_index >= 0 else snapshot["track_index"]
            target_device = device_index if device_index >= 0 else snapshot["device_index"]

            params_to_set = [{"index": p["index"], "value": p["value"]} for p in snapshot["parameters"]]

            if not params_to_set:
                return "Snapshot contains no parameters to restore."

            m4l = get_m4l_connection()
            data = _m4l_batch_set_params(m4l, target_track, target_device, params_to_set)
            ok = data["params_set"]
            failed = data["params_failed"]
            return (
                f"Restored snapshot '{snapshot['name']}' (ID: {snapshot_id})\n"
                f"Target: track {target_track}, device {target_device}\n"
                f"Parameters restored: {ok}/{len(params_to_set)} ({failed} failed)"
            )
        except ConnectionError as e:
            return f"M4L bridge not available: {e}"
        except Exception as e:
            logger.error(f"Error restoring device snapshot: {str(e)}")
            return f"Error restoring device snapshot: {str(e)}"

    @mcp.tool()
    @_tool_handler("listing snapshots")
    def list_snapshots(ctx: Context) -> str:
        """List all stored device state snapshots.

        Shows snapshot IDs, names, device info, and timestamps.
        Use snapshot IDs with restore_device_snapshot() to recall states.
        """
        with state.store_lock:
            non_group = {k: v for k, v in state.snapshot_store.items() if v.get("type") != "group"}

        if not non_group:
            return "No snapshots stored. Use snapshot_device_state() to capture a device state."

        output = f"Stored snapshots ({len(non_group)}):\n\n"
        for sid, snap in non_group.items():
            output += (
                f"  ID: {sid}\n"
                f"  Name: {snap['name']}\n"
                f"  Device: {snap.get('device_name', '?')} ({snap.get('device_class', '?')})\n"
                f"  Location: track {snap.get('track_index', '?')}, device {snap.get('device_index', '?')}\n"
                f"  Parameters: {snap.get('parameter_count', '?')}\n"
                f"  Captured: {snap.get('timestamp', '?')}\n\n"
            )
        return output

    @mcp.tool()
    @_tool_handler("deleting snapshot")
    def delete_snapshot(ctx: Context, snapshot_id: str) -> str:
        """Delete a stored device state snapshot.

        Parameters:
        - snapshot_id: The ID of the snapshot to delete
        """
        with state.store_lock:
            if snapshot_id not in state.snapshot_store:
                return f"Snapshot '{snapshot_id}' not found."
            name = state.snapshot_store[snapshot_id].get("name", snapshot_id)
            del state.snapshot_store[snapshot_id]
        return f"Deleted snapshot '{name}' (ID: {snapshot_id})."

    @mcp.tool()
    @_tool_handler("getting snapshot details")
    def get_snapshot_details(ctx: Context, snapshot_id: str) -> str:
        """Get the full parameter details of a stored snapshot.

        Parameters:
        - snapshot_id: The ID of the snapshot to inspect
        """
        with state.store_lock:
            if snapshot_id not in state.snapshot_store:
                return f"Snapshot '{snapshot_id}' not found."
            snap = state.snapshot_store[snapshot_id]

        output = (
            f"Snapshot: {snap.get('name', snapshot_id)} (ID: {snapshot_id})\n"
            f"Device: {snap.get('device_name', '?')} ({snap.get('device_class', '?')})\n"
            f"Location: track {snap.get('track_index', '?')}, device {snap.get('device_index', '?')}\n"
            f"Captured: {snap.get('timestamp', '?')}\n"
            f"Parameters ({snap.get('parameter_count', 0)}):\n\n"
        )
        for p in snap.get("parameters", []):
            quant = " [quantized]" if p.get("is_quantized") else ""
            output += (
                f"  [{p.get('index', '?')}] {p.get('name', '?')}: "
                f"{p.get('value', '?')} "
                f"(range: {p.get('min', '?')} - {p.get('max', '?')}){quant}\n"
            )
        return output

    @mcp.tool()
    @_tool_handler("deleting all snapshots")
    def delete_all_snapshots(ctx: Context) -> str:
        """Delete all stored snapshots, macros, and parameter maps.

        Clears all in-memory feature data. This cannot be undone.
        """
        with state.store_lock:
            count = len(state.snapshot_store) + len(state.macro_store) + len(state.param_map_store)
            state.snapshot_store.clear()
            state.macro_store.clear()
            state.param_map_store.clear()
        return f"Cleared all feature data: {count} items deleted."

    # ==================================================================
    # Group snapshots (multi-device / multi-track)
    # ==================================================================

    @mcp.tool()
    @_tool_handler("capturing group snapshot")
    def snapshot_all_devices(
        ctx: Context,
        track_indices: List[int],
        snapshot_name: str = ""
    ) -> str:
        """Snapshot the state of all devices across one or more tracks.

        Captures every device on the specified tracks into a group of snapshots
        that can be restored together with restore_group_snapshot().

        Parameters:
        - track_indices: List of track indices to snapshot
        - snapshot_name: Optional name for the group snapshot

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        if not isinstance(track_indices, list) or len(track_indices) == 0:
            raise ValueError("track_indices must be a non-empty list of integers.")
        for ti in track_indices:
            _validate_index(ti, "track_index")

        m4l = get_m4l_connection()
        ableton = get_ableton_connection()
        group_id = str(uuid.uuid4())[:8]
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        snapshot_ids = []
        device_count = 0

        for ti in track_indices:
            track_info = ableton.send_command("get_track_info", {"track_index": ti})
            devices = track_info.get("devices", [])

            for di, dev in enumerate(devices):
                result = m4l.send_command("discover_params", {
                    "track_index": ti,
                    "device_index": di
                })

                if result.get("status") != "success":
                    continue

                data = result.get("result", {})
                snap_id = str(uuid.uuid4())[:8]

                with state.store_lock:
                    state.snapshot_store[snap_id] = {
                        "id": snap_id,
                        "group_id": group_id,
                        "name": f"{data.get('device_name', 'Unknown')}_t{ti}_d{di}",
                        "timestamp": timestamp,
                        "track_index": ti,
                        "device_index": di,
                        "device_name": data.get("device_name", "Unknown"),
                        "device_class": data.get("device_class", "Unknown"),
                        "parameter_count": data.get("parameter_count", 0),
                        "parameters": data.get("parameters", [])
                    }
                snapshot_ids.append(snap_id)
                device_count += 1

        group_name = snapshot_name or f"group_{group_id}"

        with state.store_lock:
            state.snapshot_store[f"group_{group_id}"] = {
                "id": f"group_{group_id}",
                "type": "group",
                "name": group_name,
                "timestamp": timestamp,
                "track_indices": track_indices,
                "snapshot_ids": snapshot_ids,
                "device_count": device_count
            }

        return (
            f"Group snapshot '{group_name}' saved (ID: group_{group_id})\n"
            f"Tracks: {track_indices}\n"
            f"Devices captured: {device_count}\n"
            f"Individual snapshot IDs: {', '.join(snapshot_ids)}"
        )

    @mcp.tool()
    @_tool_handler("restoring group snapshot")
    def restore_group_snapshot(ctx: Context, group_id: str) -> str:
        """Restore all device states from a group snapshot.

        Restores every device captured in a snapshot_all_devices() call.

        Parameters:
        - group_id: The group snapshot ID (starts with 'group_')

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        with state.store_lock:
            if group_id not in state.snapshot_store:
                return f"Group snapshot '{group_id}' not found."
            group = state.snapshot_store[group_id]

        if group.get("type") != "group":
            return f"'{group_id}' is not a group snapshot. Use restore_device_snapshot() instead."

        m4l = get_m4l_connection()
        total_devices = 0
        total_params = 0
        total_failed = 0

        for snap_id in group.get("snapshot_ids", []):
            with state.store_lock:
                if snap_id not in state.snapshot_store:
                    continue
                snap = state.snapshot_store[snap_id]

            params_to_set = [{"index": p["index"], "value": p["value"]} for p in snap.get("parameters", [])]

            if not params_to_set:
                continue

            data = _m4l_batch_set_params(m4l, snap["track_index"], snap["device_index"], params_to_set)
            total_params += data["params_set"]
            total_failed += data["params_failed"]
            total_devices += 1

        return (
            f"Restored group snapshot '{group['name']}'\n"
            f"Devices restored: {total_devices}\n"
            f"Parameters restored: {total_params} ({total_failed} failed)"
        )

    @mcp.tool()
    @_tool_handler("comparing snapshots")
    def compare_snapshots(ctx: Context, snapshot_a_id: str, snapshot_b_id: str) -> str:
        """Compare two device snapshots and show parameter differences.

        Useful for understanding what changed between two states.

        Parameters:
        - snapshot_a_id: First snapshot ID
        - snapshot_b_id: Second snapshot ID
        """
        with state.store_lock:
            if snapshot_a_id not in state.snapshot_store:
                return f"Snapshot '{snapshot_a_id}' not found."
            if snapshot_b_id not in state.snapshot_store:
                return f"Snapshot '{snapshot_b_id}' not found."
            snap_a = state.snapshot_store[snapshot_a_id]
            snap_b = state.snapshot_store[snapshot_b_id]

        a_by_index = {p["index"]: p for p in snap_a.get("parameters", [])}
        b_by_index = {p["index"]: p for p in snap_b.get("parameters", [])}

        all_indices = sorted(set(a_by_index.keys()) | set(b_by_index.keys()))

        changed = []
        unchanged = 0

        for idx in all_indices:
            in_a = idx in a_by_index
            in_b = idx in b_by_index

            if in_a and in_b:
                val_a = a_by_index[idx]["value"]
                val_b = b_by_index[idx]["value"]
                if abs(val_a - val_b) > 0.001:
                    changed.append({
                        "index": idx,
                        "name": a_by_index[idx].get("name", "?"),
                        "value_a": val_a,
                        "value_b": val_b,
                        "delta": val_b - val_a
                    })
                else:
                    unchanged += 1
            else:
                unchanged += 1

        output = (
            f"Comparison: '{snap_a.get('name', snapshot_a_id)}' vs '{snap_b.get('name', snapshot_b_id)}'\n"
            f"Changed: {len(changed)} | Unchanged: {unchanged}\n\n"
        )

        if changed:
            output += "Changed parameters:\n"
            for c in changed:
                direction = "+" if c["delta"] > 0 else ""
                output += (
                    f"  [{c['index']}] {c['name']}: "
                    f"{c['value_a']:.4f} -> {c['value_b']:.4f} "
                    f"({direction}{c['delta']:.4f})\n"
                )
        else:
            output += "No parameter differences found.\n"

        return output

    # ==================================================================
    # Preset morph engine
    # ==================================================================

    @mcp.tool()
    @_tool_handler("during morph")
    def morph_between_snapshots(
        ctx: Context,
        snapshot_a_id: str,
        snapshot_b_id: str,
        position: float,
        track_index: int = -1,
        device_index: int = -1
    ) -> str:
        """Morph between two device snapshots by interpolating all parameters.

        Takes two previously captured snapshots and smoothly blends between them.
        Position 0.0 = fully snapshot A, position 1.0 = fully snapshot B.
        Quantized parameters (e.g. waveform selectors) snap at the midpoint.

        Parameters:
        - snapshot_a_id: ID of the first snapshot (position 0.0)
        - snapshot_b_id: ID of the second snapshot (position 1.0)
        - position: Morph position (0.0 to 1.0)
        - track_index: Override target track (-1 = use snapshot A's track)
        - device_index: Override target device (-1 = use snapshot A's device)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_range(position, "position", 0.0, 1.0)

        with state.store_lock:
            if snapshot_a_id not in state.snapshot_store:
                return f"Snapshot A '{snapshot_a_id}' not found."
            if snapshot_b_id not in state.snapshot_store:
                return f"Snapshot B '{snapshot_b_id}' not found."
            snap_a = state.snapshot_store[snapshot_a_id]
            snap_b = state.snapshot_store[snapshot_b_id]

        target_track = track_index if track_index >= 0 else snap_a["track_index"]
        target_device = device_index if device_index >= 0 else snap_a["device_index"]

        b_by_index = {p["index"]: p for p in snap_b.get("parameters", [])}

        params_to_set = []
        skipped = 0
        for p_a in snap_a.get("parameters", []):
            idx = p_a["index"]
            if idx not in b_by_index:
                skipped += 1
                continue

            p_b = b_by_index[idx]
            val_a = p_a["value"]
            val_b = p_b["value"]

            if p_a.get("is_quantized", False):
                interpolated = val_a if position < 0.5 else val_b
            else:
                interpolated = val_a + (val_b - val_a) * position

            params_to_set.append({"index": idx, "value": interpolated})

        if not params_to_set:
            return "No matching parameters found between the two snapshots."

        m4l = get_m4l_connection()
        data = _m4l_batch_set_params(m4l, target_track, target_device, params_to_set)
        ok = data["params_set"]
        return (
            f"Morph at position {position:.2f} "
            f"('{snap_a.get('name', snapshot_a_id)}' -> '{snap_b.get('name', snapshot_b_id)}')\n"
            f"Interpolated {ok} parameters, skipped {skipped} (unmatched)\n"
            f"Target: track {target_track}, device {target_device}"
        )

    # ==================================================================
    # Smart macro controller
    # ==================================================================

    @mcp.tool()
    @_tool_handler("creating macro controller")
    def create_macro_controller(
        ctx: Context,
        name: str,
        mappings: List[Dict[str, Any]]
    ) -> str:
        """Create a macro controller that links multiple device parameters together.

        A macro controller maps a single 0.0-1.0 value to multiple device parameters,
        each with their own range mapping.

        Parameters:
        - name: Human-readable name for the macro (e.g., "Brightness", "Intensity")
        - mappings: List of parameter mappings, each with:
            - track_index: int
            - device_index: int
            - parameter_index: int (LOM index from discover_device_params)
            - min_value: float (parameter value when macro = 0.0)
            - max_value: float (parameter value when macro = 1.0)

        After creation, use set_macro_value() to control all linked parameters at once.

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        if not isinstance(mappings, list) or len(mappings) == 0:
            raise ValueError("mappings must be a non-empty list.")
        required = {"track_index", "device_index", "parameter_index", "min_value", "max_value"}
        for i, m in enumerate(mappings):
            if not isinstance(m, dict):
                raise ValueError(f"Mapping at index {i} must be a dictionary.")
            missing = required - m.keys()
            if missing:
                raise ValueError(f"Mapping at index {i} missing keys: {', '.join(sorted(missing))}")

        macro_id = str(uuid.uuid4())[:8]
        with state.store_lock:
            state.macro_store[macro_id] = {
                "id": macro_id,
                "name": name,
                "mappings": mappings,
                "current_value": 0.0,
                "created": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        output = (
            f"Macro controller '{name}' created (ID: {macro_id})\n"
            f"Linked parameters: {len(mappings)}\n"
            f"Use set_macro_value('{macro_id}', value) to control (0.0-1.0)\n\n"
            f"Mappings:\n"
        )
        for m in mappings:
            output += (
                f"  - Track {m['track_index']}, Device {m['device_index']}, "
                f"Param [{m['parameter_index']}]: "
                f"{m['min_value']} -> {m['max_value']}\n"
            )

        return output

    @mcp.tool()
    @_tool_handler("setting macro value")
    def set_macro_value(ctx: Context, macro_id: str, value: float) -> str:
        """Set the value of a macro controller, updating all linked parameters.

        Interpolates the macro value (0.0-1.0) across all mapped parameters
        and applies them via batch set.

        Parameters:
        - macro_id: The ID of the macro controller
        - value: The macro value (0.0 to 1.0)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        with state.store_lock:
            if macro_id not in state.macro_store:
                return f"Macro '{macro_id}' not found. Use list_macros() to see available macros."
            _validate_range(value, "value", 0.0, 1.0)
            macro = state.macro_store[macro_id]
            macro["current_value"] = value

        grouped: Dict[tuple, list] = {}
        for m in macro["mappings"]:
            key = (m["track_index"], m["device_index"])
            interpolated = m["min_value"] + (m["max_value"] - m["min_value"]) * value
            if key not in grouped:
                grouped[key] = []
            grouped[key].append({"index": m["parameter_index"], "value": interpolated})

        m4l = get_m4l_connection()
        total_set = 0
        total_failed = 0

        for (ti, di), params in grouped.items():
            data = _m4l_batch_set_params(m4l, ti, di, params)
            total_set += data["params_set"]
            total_failed += data["params_failed"]

        return (
            f"Macro '{macro['name']}' set to {value:.2f}\n"
            f"Updated {total_set} parameters across {len(grouped)} device(s) "
            f"({total_failed} failed)"
        )

    @mcp.tool()
    @_tool_handler("listing macros")
    def list_macros(ctx: Context) -> str:
        """List all created macro controllers.

        Shows macro IDs, names, number of linked parameters, and current values.
        """
        with state.store_lock:
            if not state.macro_store:
                return "No macro controllers created. Use create_macro_controller() to create one."

            output = f"Macro controllers ({len(state.macro_store)}):\n\n"
            for mid, macro in state.macro_store.items():
                output += (
                    f"  ID: {mid}\n"
                    f"  Name: {macro['name']}\n"
                    f"  Linked params: {len(macro['mappings'])}\n"
                    f"  Current value: {macro['current_value']:.2f}\n"
                    f"  Created: {macro['created']}\n\n"
                )
        return output

    @mcp.tool()
    @_tool_handler("deleting macro")
    def delete_macro(ctx: Context, macro_id: str) -> str:
        """Delete a macro controller.

        Parameters:
        - macro_id: The ID of the macro to delete
        """
        with state.store_lock:
            if macro_id not in state.macro_store:
                return f"Macro '{macro_id}' not found."
            name = state.macro_store[macro_id]["name"]
            del state.macro_store[macro_id]
        return f"Deleted macro controller '{name}' (ID: {macro_id})."

    # ==================================================================
    # Intelligent preset generator
    # ==================================================================

    @mcp.tool()
    @_tool_handler("during preset generation")
    def generate_preset(
        ctx: Context,
        track_index: int,
        device_index: int,
        description: str,
        variation_count: int = 1
    ) -> str:
        """Generate an intelligent preset for a device based on a text description.

        Discovers all parameters on the target device and returns them so Claude can
        intelligently set values based on the description (e.g., "bright bass",
        "warm pad", "aggressive lead"). The current state is auto-saved as a snapshot
        for easy revert.

        After calling this tool, use batch_set_hidden_parameters() to apply the preset.
        Use restore_device_snapshot() with the revert snapshot ID to undo.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device on the track
        - description: Text description of the desired sound (e.g., "bright plucky bass")
        - variation_count: How many variations to suggest (default: 1)

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        if variation_count < 1 or variation_count > 5:
            raise ValueError("variation_count must be between 1 and 5.")

        m4l = get_m4l_connection()
        result = m4l.send_command("discover_params", {
            "track_index": track_index,
            "device_index": device_index
        })

        if result.get("status") != "success":
            return f"M4L bridge error: {result.get('message', 'Unknown error')}"

        data = result.get("result", {})
        device_name = data.get("device_name", "Unknown")
        device_class = data.get("device_class", "Unknown")
        params = data.get("parameters", [])

        # Auto-snapshot current state for revert
        snapshot_id = str(uuid.uuid4())[:8]
        with state.store_lock:
            state.snapshot_store[snapshot_id] = {
                "id": snapshot_id,
                "name": f"pre_preset_{device_name}_{snapshot_id}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "track_index": track_index,
                "device_index": device_index,
                "device_name": device_name,
                "device_class": device_class,
                "parameter_count": len(params),
                "parameters": params
            }

        output = (
            f"PRESET GENERATION for: '{description}'\n"
            f"Device: {device_name} ({device_class}) on track {track_index}, device {device_index}\n"
            f"Variations requested: {variation_count}\n"
            f"Revert snapshot ID: {snapshot_id} (use restore_device_snapshot to undo)\n\n"
            f"Device has {len(params)} parameters:\n\n"
        )

        for p in params:
            quant = " [quantized]" if p.get("is_quantized") else ""
            items = f" options: {p.get('value_items')}" if p.get("value_items") else ""
            output += (
                f"  [{p['index']}] {p.get('name', '?')}: "
                f"current={p.get('value', '?')} "
                f"(range: {p.get('min', '?')}-{p.get('max', '?')}"
                f", default={p.get('default_value', '?')}){quant}{items}\n"
            )

        output += (
            f"\nNow calculate appropriate values for each parameter based on the description "
            f"'{description}' and device type '{device_class}'. Then call "
            f"batch_set_hidden_parameters(track_index={track_index}, device_index={device_index}, "
            f"parameters=[...]) with the calculated values."
        )

        return output

    # ==================================================================
    # VST/AU parameter mapper
    # ==================================================================

    @mcp.tool()
    @_tool_handler("creating parameter map")
    def create_parameter_map(
        ctx: Context,
        track_index: int,
        device_index: int,
        friendly_names: List[Dict[str, Any]]
    ) -> str:
        """Create a custom parameter map with friendly names for a device's parameters.

        Stores a mapping from cryptic parameter names/indices to human-readable names.
        Particularly useful for VST/AU plugins with obscure parameter names.

        Parameters:
        - track_index: The index of the track containing the device
        - device_index: The index of the device on the track
        - friendly_names: List of mappings, each with:
            - parameter_index: int (LOM index)
            - original_name: str (the parameter's actual name)
            - friendly_name: str (human-readable name)
            - category: str (optional grouping like "Filter", "Oscillator", "Envelope")

        Requires the AbletonBridge M4L device to be loaded on any track.
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        if not isinstance(friendly_names, list) or len(friendly_names) == 0:
            raise ValueError("friendly_names must be a non-empty list.")

        m4l = get_m4l_connection()
        result = m4l.send_command("discover_params", {
            "track_index": track_index,
            "device_index": device_index
        })

        data = _m4l_result(result)
        device_name = data.get("device_name", "Unknown")
        device_class = data.get("device_class", "Unknown")

        map_id = str(uuid.uuid4())[:8]
        with state.store_lock:
            state.param_map_store[map_id] = {
                "id": map_id,
                "track_index": track_index,
                "device_index": device_index,
                "device_name": device_name,
                "device_class": device_class,
                "mappings": friendly_names,
                "created": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        output = (
            f"Parameter map created for '{device_name}' (ID: {map_id})\n"
            f"Mapped parameters: {len(friendly_names)}\n\n"
        )

        categories: Dict[str, list] = {}
        for fn in friendly_names:
            cat = fn.get("category", "Uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(fn)

        for cat, maps in categories.items():
            output += f"  [{cat}]\n"
            for m in maps:
                output += (
                    f"    [{m.get('parameter_index', '?')}] "
                    f"'{m.get('original_name', '?')}' -> "
                    f"'{m.get('friendly_name', '?')}'\n"
                )
            output += "\n"

        return output

    @mcp.tool()
    @_tool_handler("getting parameter map")
    def get_parameter_map(ctx: Context, map_id: str) -> str:
        """Retrieve a stored parameter map with friendly names.

        Parameters:
        - map_id: The ID of the parameter map to retrieve
        """
        with state.store_lock:
            if map_id not in state.param_map_store:
                return f"Parameter map '{map_id}' not found."
            return json.dumps(state.param_map_store[map_id])

    @mcp.tool()
    @_tool_handler("listing parameter maps")
    def list_parameter_maps(ctx: Context) -> str:
        """List all stored parameter maps."""
        with state.store_lock:
            if not state.param_map_store:
                return "No parameter maps stored. Use create_parameter_map() to create one."

            output = f"Parameter maps ({len(state.param_map_store)}):\n\n"
            for mid, pmap in state.param_map_store.items():
                output += (
                    f"  ID: {mid}\n"
                    f"  Device: {pmap.get('device_name', '?')} ({pmap.get('device_class', '?')})\n"
                    f"  Location: track {pmap.get('track_index', '?')}, device {pmap.get('device_index', '?')}\n"
                    f"  Mapped params: {len(pmap.get('mappings', []))}\n"
                    f"  Created: {pmap.get('created', '?')}\n\n"
                )
        return output

    @mcp.tool()
    @_tool_handler("deleting parameter map")
    def delete_parameter_map(ctx: Context, map_id: str) -> str:
        """Delete a stored parameter map.

        Parameters:
        - map_id: The ID of the parameter map to delete
        """
        with state.store_lock:
            if map_id not in state.param_map_store:
                return f"Parameter map '{map_id}' not found."
            name = state.param_map_store[map_id].get("device_name", map_id)
            del state.param_map_store[map_id]
        return f"Deleted parameter map for '{name}' (ID: {map_id})."
