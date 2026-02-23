"""Pure constants for AbletonBridge MCP server.

Nothing in this module is mutable at runtime. Values that were previously
defined as module-level ``_UPPER_CASE`` globals in server.py (and as class
attributes on ``AbletonConnection``) are gathered here so every module can
do ``from MCP_Server.constants import ...`` without circular imports.

Variable names have **no** underscore prefix.
"""

import os
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Tiered command delays for stability
# ---------------------------------------------------------------------------

# Tier 0: No delay -- instant property setters and navigation commands
TIER_0_COMMANDS: frozenset = frozenset([
    "set_tempo", "set_track_name", "set_clip_name", "set_track_color",
    "set_clip_color", "set_track_mute", "set_track_solo", "set_track_arm",
    "set_metronome", "set_track_pan", "set_track_volume",
    "set_return_track_volume", "set_return_track_pan", "set_track_send",
    "set_master_volume", "start_playback", "stop_playback",
    "undo", "redo", "set_song_time", "set_song_loop",
    "set_clip_looping", "set_device_parameter", "set_device_enabled",
    "fire_clip", "stop_clip", "fire_scene",
    "select_scene", "select_track", "set_detail_clip",
    "set_track_fold", "set_crossfade_assign",
    "set_track_monitoring", "set_clip_launch_mode",
    "set_clip_launch_quantization", "set_clip_legato",
    "set_scene_name", "set_scene_tempo", "tap_tempo",
    "set_arrangement_overdub", "set_track_routing", "navigate_playback",
    "set_clip_pitch", "set_groove_settings", "set_song_settings",
    "trigger_session_record", "set_or_delete_cue", "jump_to_cue",
    "preview_browser_item", "move_clip_playing_pos",
    "set_transmute_properties", "rack_variation_action",
    "set_return_track_mute", "set_return_track_solo", "set_clip_grid",
])

# Tier 1: Light delay (50ms post-delay only) -- note/clip/automation operations
TIER_1_COMMANDS: frozenset = frozenset([
    "add_notes_to_clip", "add_notes_extended", "remove_notes_range",
    "clear_clip_notes", "quantize_clip_notes", "transpose_clip_notes",
    "set_clip_loop_points", "set_clip_start_end",
    "create_clip_automation", "clear_clip_automation",
    "create_track_automation", "clear_track_automation",
    "duplicate_clip", "duplicate_clip_loop", "duplicate_clip_region",
    "crop_clip", "reverse_clip", "set_clip_warp", "set_warp_mode",
    "apply_groove", "set_drum_pad", "copy_drum_pad", "capture_midi",
    "set_compressor_sidechain", "set_eq8_properties",
    "set_simpler_properties", "simpler_sample_action", "manage_sample_slices",
    "set_hybrid_reverb_ir", "duplicate_clip_to_arrangement",
])

# Tier 2: Heavy delay (100ms pre + 100ms post) -- structural/loading changes
TIER_2_COMMANDS: frozenset = frozenset([
    "create_midi_track", "create_audio_track", "create_clip",
    "delete_clip", "delete_track", "duplicate_track",
    "create_return_track", "create_scene", "delete_scene",
    "load_instrument_or_effect", "load_sample", "load_drum_kit",
    "group_tracks", "freeze_track", "unfreeze_track",
    "audio_to_midi", "create_midi_track_with_simpler",
    "sliced_simpler_to_drum_rack", "delete_device",
    "delete_time", "duplicate_time", "insert_silence",
    "arm_track", "disarm_track",
    "start_arrangement_recording", "stop_arrangement_recording",
    "set_loop_start", "set_loop_end", "set_loop_length", "set_playback_position",
])

# Combined set of all modifying commands (union of all tiers)
MODIFYING_COMMANDS: frozenset = TIER_0_COMMANDS | TIER_1_COMMANDS | TIER_2_COMMANDS

# ---------------------------------------------------------------------------
# Browser categories
# ---------------------------------------------------------------------------

# Root browser categories: (path_root, display_name)
# path_root uses the lowercase attribute name so paths work directly with
# get_browser_items_at_path (which lowercases the first component).
BROWSER_CATEGORIES: List[Tuple[str, str]] = [
    ("instruments", "Instruments"),
    ("drums", "Drums"),
    ("audio_effects", "Audio Effects"),
    ("midi_effects", "MIDI Effects"),
    ("max_for_live", "Max for Live"),
    ("plugins", "Plug-ins"),
    ("user_library", "User Library"),
]

BROWSER_CACHE_MAX_DEPTH: int = 3    # category/device/subcategory (skip preset files)
BROWSER_CACHE_MAX_ITEMS: int = 1500

# Maps category keys to display names (used by search_browser and get_browser_tree)
CATEGORY_DISPLAY: Dict[str, str] = {
    "instruments": "Instruments",
    "sounds": "Sounds",
    "drums": "Drums",
    "audio_effects": "Audio Effects",
    "midi_effects": "MIDI Effects",
    "max_for_live": "Max for Live",
    "plugins": "Plug-ins",
    "clips": "Clips",
    "samples": "Samples",
    "packs": "Packs",
    "user_library": "User Library",
}

# Category priority for resolving name collisions in device_uri_map.
# Lower number = higher priority (stock devices beat preset folders).
CATEGORY_PRIORITY: Dict[str, int] = {
    "Instruments": 0,
    "Audio Effects": 1,
    "MIDI Effects": 2,
    "Max for Live": 3,
    "Plug-ins": 4,
    "Sounds": 5,
    "Drums": 6,
    "Clips": 7,
    "Samples": 8,
    "Packs": 9,
    "User Library": 10,
}

# ---------------------------------------------------------------------------
# Browser disk cache
# ---------------------------------------------------------------------------

BROWSER_CACHE_TTL: float = 604800.0          # 7 days -- only refresh_browser_cache forces a rescan
BROWSER_DISK_CACHE_MAX_AGE: float = 604800.0  # 7 days -- disk cache ignored if older

BROWSER_DISK_CACHE_DIR: str = os.path.join(os.path.expanduser("~"), ".ableton-bridge")
BROWSER_DISK_CACHE_PATH: str = os.path.join(BROWSER_DISK_CACHE_DIR, "browser_cache.json.gz")
BROWSER_DISK_CACHE_PATH_LEGACY: str = os.path.join(BROWSER_DISK_CACHE_DIR, "browser_cache.json")
