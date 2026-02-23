"""Compound workflow tools for AbletonBridge.

These high-level tools orchestrate multiple Remote Script commands in a single
MCP tool call, reducing round-trip overhead by 3-5x for common workflows.
"""
import json
import logging
from typing import List, Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _m4l_result
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.connections.m4l import get_m4l_connection
from MCP_Server.cache.browser import resolve_device_uri
from MCP_Server.validation import _validate_index, _validate_index_allow_negative, _validate_range, _validate_notes
import MCP_Server.state as state

logger = logging.getLogger("AbletonBridge")


def register_tools(mcp):
    """Register compound workflow tools with the MCP server."""

    @mcp.tool()
    @_tool_handler("creating instrument track")
    def create_instrument_track(
        ctx: Context,
        instrument_name: str,
        track_name: str = "",
        index: int = -1,
        color_index: int = -1,
    ) -> str:
        """Create a new MIDI track and load an instrument in one step.

        Combines create_midi_track + load_instrument_or_effect + set_track_name + set_track_color
        into a single tool call (saves 3-4 round trips).

        Parameters:
        - instrument_name: Name of instrument to load (e.g. "Wavetable", "Drift", "Operator")
        - track_name: Optional name for the track (defaults to instrument name)
        - index: Track position (-1 = end of list)
        - color_index: Optional color index (0-69, -1 = no change)
        """
        _validate_index_allow_negative(index, "index", min_value=-1)
        ableton = get_ableton_connection()

        # Step 1: Create the MIDI track
        result = ableton.send_command("create_midi_track", {"index": index})
        track_idx = result.get("index", 0)

        # Step 2: Resolve and load the instrument
        uri = resolve_device_uri(instrument_name)
        try:
            ableton.send_command("load_instrument_or_effect", {
                "track_index": track_idx, "uri": uri
            })
        except Exception as e:
            logger.warning("Failed to load instrument '%s': %s", instrument_name, e)

        # Step 3: Set track name
        name = track_name or instrument_name
        try:
            ableton.send_command("set_track_name", {
                "track_index": track_idx, "name": name
            })
        except Exception:
            pass

        # Step 4: Set track color (if specified)
        if color_index >= 0:
            try:
                ableton.send_command("set_track_color", {
                    "track_index": track_idx, "color_index": color_index
                })
            except Exception:
                pass

        return json.dumps({
            "track_index": track_idx,
            "instrument": instrument_name,
            "name": name,
            "uri": uri,
        })

    @mcp.tool()
    @_tool_handler("creating clip with notes")
    def create_clip_with_notes(
        ctx: Context,
        track_index: int,
        clip_index: int,
        length: float,
        notes: list,
        clip_name: str = "",
    ) -> str:
        """Create a new MIDI clip and add notes in one step.

        Combines create_clip + add_notes_to_clip + set_clip_name into a single call.

        Parameters:
        - track_index: Target track index
        - clip_index: Target clip slot index
        - length: Clip length in beats
        - notes: List of note dicts with pitch, start_time, duration, velocity
        - clip_name: Optional name for the clip
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        _validate_notes(notes)
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError(f"length must be a positive number, got {length}")

        ableton = get_ableton_connection()

        # Step 1: Create the clip
        ableton.send_command("create_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "length": length,
        })

        # Step 2: Add notes
        ableton.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })

        # Step 3: Set name (if provided)
        if clip_name:
            try:
                ableton.send_command("set_clip_name", {
                    "track_index": track_index,
                    "clip_index": clip_index,
                    "name": clip_name,
                })
            except Exception:
                pass

        return json.dumps({
            "track_index": track_index,
            "clip_index": clip_index,
            "length": length,
            "note_count": len(notes),
            "name": clip_name or "(unnamed)",
        })

    @mcp.tool()
    @_tool_handler("setting up send/return")
    def setup_send_return(
        ctx: Context,
        effect_name: str,
        return_name: str = "",
        source_tracks: list = None,
        send_level: float = 0.5,
    ) -> str:
        """Create a return track with an effect and optionally set send levels.

        Combines create_return_track + load_instrument_or_effect + set_track_name
        + N x set_track_send into a single call.

        Parameters:
        - effect_name: Name of effect to load (e.g. "Reverb", "Delay", "Chorus-Ensemble")
        - return_name: Optional name for the return track
        - source_tracks: Optional list of track indices to set send levels on
        - send_level: Send level for source tracks (0.0 to 1.0, default 0.5)
        """
        _validate_range(send_level, "send_level", 0.0, 1.0)
        ableton = get_ableton_connection()

        # Step 1: Create return track
        result = ableton.send_command("create_return_track")
        return_idx = result.get("index", 0)

        # Step 2: Load effect
        uri = resolve_device_uri(effect_name)
        try:
            ableton.send_command("load_instrument_or_effect", {
                "track_index": return_idx,
                "uri": uri,
                "track_type": "return",
            })
        except Exception as e:
            logger.warning("Failed to load effect '%s' on return: %s", effect_name, e)

        # Step 3: Name the return track
        name = return_name or effect_name
        try:
            ableton.send_command("set_track_name", {
                "track_index": return_idx,
                "name": name,
                "track_type": "return",
            })
        except Exception:
            pass

        # Step 4: Set send levels on source tracks
        sends_set = 0
        if source_tracks:
            # Need to figure out which send index this new return is
            returns_info = ableton.send_command("get_return_tracks")
            send_index = len(returns_info.get("tracks", [])) - 1  # new return is last
            for track_idx in source_tracks:
                try:
                    ableton.send_command("set_track_send", {
                        "track_index": track_idx,
                        "send_index": send_index,
                        "value": send_level,
                    })
                    sends_set += 1
                except Exception as e:
                    logger.warning("Failed to set send on track %d: %s", track_idx, e)

        return json.dumps({
            "return_index": return_idx,
            "effect": effect_name,
            "name": name,
            "sends_set": sends_set,
        })

    @mcp.tool()
    @_tool_handler("getting full session state")
    def get_full_session_state(ctx: Context) -> str:
        """Get complete session state in one call (session info + all tracks + scenes).

        Combines get_session_info + get_all_tracks_info + get_return_tracks_info + get_scenes
        into a single tool call (saves 3 round trips).
        """
        ableton = get_ableton_connection()

        session = ableton.send_command("get_session_info")
        tracks = ableton.send_command("get_all_tracks_info")
        returns = ableton.send_command("get_return_tracks")
        scenes = ableton.send_command("get_scenes")

        return json.dumps({
            "session": session,
            "tracks": tracks,
            "return_tracks": returns,
            "scenes": scenes,
        })

    @mcp.tool()
    @_tool_handler("applying effect chain")
    def apply_effect_chain(
        ctx: Context,
        track_index: int,
        effects: list,
        track_type: str = "track",
    ) -> str:
        """Load multiple effects onto a track sequentially.

        Parameters:
        - track_index: Target track index
        - effects: List of effect names (e.g. ["EQ Eight", "Compressor", "Limiter"])
        - track_type: "track", "return", or "master"
        """
        _validate_index(track_index, "track_index")
        if not isinstance(effects, list) or len(effects) == 0:
            raise ValueError("effects must be a non-empty list of effect names")

        ableton = get_ableton_connection()
        loaded = []
        failed = []

        for effect_name in effects:
            uri = resolve_device_uri(effect_name)
            try:
                ableton.send_command("load_instrument_or_effect", {
                    "track_index": track_index,
                    "uri": uri,
                    "track_type": track_type,
                })
                loaded.append(effect_name)
            except Exception as e:
                failed.append({"effect": effect_name, "error": str(e)})
                logger.warning("Failed to load effect '%s': %s", effect_name, e)

        return json.dumps({
            "track_index": track_index,
            "loaded": loaded,
            "failed": failed,
        })

    @mcp.tool()
    @_tool_handler("batch setting mixer")
    def batch_set_mixer(
        ctx: Context,
        settings: list,
    ) -> str:
        """Set mixer parameters for multiple tracks at once.

        Each setting is a dict with track_index and optional volume, pan, mute, solo.
        Saves N round trips vs. calling individual set_track_* tools.

        Parameters:
        - settings: List of dicts, each with:
          - track_index (required): Track index
          - track_type (optional): "track", "return", or "master" (default "track")
          - volume (optional): 0.0 to 1.0
          - pan (optional): -1.0 to 1.0
          - mute (optional): bool
          - solo (optional): bool
        """
        if not isinstance(settings, list) or len(settings) == 0:
            raise ValueError("settings must be a non-empty list")

        ableton = get_ableton_connection()
        applied = 0
        errors = []

        for i, setting in enumerate(settings):
            if not isinstance(setting, dict) or "track_index" not in setting:
                errors.append({"index": i, "error": "missing track_index"})
                continue

            track_idx = setting["track_index"]
            track_type = setting.get("track_type", "track")

            if "volume" in setting:
                try:
                    cmd = {"set_track_volume": "track", "set_return_track_volume": "return", "set_master_volume": "master"}
                    if track_type == "master":
                        ableton.send_command("set_master_volume", {"volume": setting["volume"]})
                    elif track_type == "return":
                        ableton.send_command("set_return_track_volume", {
                            "track_index": track_idx, "volume": setting["volume"]
                        })
                    else:
                        ableton.send_command("set_track_volume", {
                            "track_index": track_idx, "volume": setting["volume"]
                        })
                    applied += 1
                except Exception as e:
                    errors.append({"index": i, "param": "volume", "error": str(e)})

            if "pan" in setting:
                try:
                    if track_type == "return":
                        ableton.send_command("set_return_track_pan", {
                            "track_index": track_idx, "pan": setting["pan"]
                        })
                    else:
                        ableton.send_command("set_track_pan", {
                            "track_index": track_idx, "pan": setting["pan"]
                        })
                    applied += 1
                except Exception as e:
                    errors.append({"index": i, "param": "pan", "error": str(e)})

            if "mute" in setting:
                try:
                    if track_type == "return":
                        ableton.send_command("set_return_track_mute", {
                            "track_index": track_idx, "mute": setting["mute"]
                        })
                    else:
                        ableton.send_command("set_track_mute", {
                            "track_index": track_idx, "mute": setting["mute"]
                        })
                    applied += 1
                except Exception as e:
                    errors.append({"index": i, "param": "mute", "error": str(e)})

            if "solo" in setting:
                try:
                    if track_type == "return":
                        ableton.send_command("set_return_track_solo", {
                            "track_index": track_idx, "solo": setting["solo"]
                        })
                    else:
                        ableton.send_command("set_track_solo", {
                            "track_index": track_idx, "solo": setting["solo"]
                        })
                    applied += 1
                except Exception as e:
                    errors.append({"index": i, "param": "solo", "error": str(e)})

        return json.dumps({
            "settings_processed": len(settings),
            "params_applied": applied,
            "errors": errors,
        })

    @mcp.tool()
    @_tool_handler("saving effect chain template")
    def save_effect_chain(
        ctx: Context,
        track_index: int,
        template_name: str,
        track_type: str = "track",
    ) -> str:
        """Save the current device chain of a track as a reusable template.

        Captures the ordered list of devices and their parameters for later recall.

        Parameters:
        - track_index: Track to save the chain from
        - template_name: Name for the template
        - track_type: "track", "return", or "master"
        """
        _validate_index(track_index, "track_index")
        if not template_name or not template_name.strip():
            raise ValueError("template_name must be a non-empty string")

        ableton = get_ableton_connection()

        # Get track info to find devices
        if track_type == "return":
            track_info = ableton.send_command("get_return_track_info", {"track_index": track_index})
        elif track_type == "master":
            track_info = ableton.send_command("get_master_track_info")
        else:
            track_info = ableton.send_command("get_track_info", {"track_index": track_index})

        devices = track_info.get("devices", [])
        chain_data = []

        for i, dev in enumerate(devices):
            dev_info = {
                "name": dev.get("name", ""),
                "class_name": dev.get("class_name", ""),
                "index": i,
            }
            # Try to get parameters for each device
            try:
                params = ableton.send_command("get_device_parameters", {
                    "track_index": track_index,
                    "device_index": i,
                    "track_type": track_type,
                })
                dev_info["parameters"] = params.get("parameters", [])
            except Exception:
                dev_info["parameters"] = []
            chain_data.append(dev_info)

        template = {
            "name": template_name.strip(),
            "devices": chain_data,
            "source_track_type": track_type,
        }

        with state.store_lock:
            state.effect_chain_store[template_name.strip()] = template

        return json.dumps({
            "template_name": template_name.strip(),
            "device_count": len(chain_data),
        })

    @mcp.tool()
    @_tool_handler("loading effect chain template")
    def load_effect_chain(
        ctx: Context,
        track_index: int,
        template_name: str,
        track_type: str = "track",
    ) -> str:
        """Load a saved effect chain template onto a track.

        Loads each device in order and attempts to restore parameters.

        Parameters:
        - track_index: Target track index
        - template_name: Name of the template to load
        - track_type: "track", "return", or "master"
        """
        _validate_index(track_index, "track_index")

        with state.store_lock:
            store = state.effect_chain_store
            template = store.get(template_name)

        if not template:
            raise ValueError(f"Effect chain template '{template_name}' not found")

        ableton = get_ableton_connection()
        loaded = []
        failed = []

        for dev_data in template["devices"]:
            dev_name = dev_data.get("name", "")
            uri = resolve_device_uri(dev_name)
            try:
                ableton.send_command("load_instrument_or_effect", {
                    "track_index": track_index,
                    "uri": uri,
                    "track_type": track_type,
                })
                loaded.append(dev_name)
            except Exception as e:
                failed.append({"device": dev_name, "error": str(e)})

        return json.dumps({
            "template_name": template_name,
            "loaded": loaded,
            "failed": failed,
        })

    @mcp.tool()
    @_tool_handler("listing effect chain templates")
    def list_effect_chain_templates(ctx: Context) -> str:
        """List all saved effect chain templates."""
        with state.store_lock:
            store = state.effect_chain_store
            templates = []
            for name, template in store.items():
                templates.append({
                    "name": name,
                    "device_count": len(template.get("devices", [])),
                })

        return json.dumps({"templates": templates})
