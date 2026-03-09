"""MCP server instructions for AbletonBridge.

Injected into the client's system context during initialization to guide
cross-tool usage patterns. See: https://blog.modelcontextprotocol.io/posts/2025-11-03-using-server-instructions/
"""

SERVER_INSTRUCTIONS = """
AbletonBridge provides 341 tools for controlling Ableton Live sessions. This guidance covers cross-tool relationships, sequencing, and constraints not documented on individual tools.

## Startup

Call get_server_capabilities first in every session. It reports connection status, M4L bridge availability, browser cache state, and tool count. Many tools fail silently or return unhelpful errors without a live Ableton connection — checking capabilities first avoids wasted calls.

## Workflow Sequencing

Common multi-tool workflows follow these canonical sequences:

- **Track creation**: Use the compound tool create_instrument_track (creates track + loads instrument + names it in one call). For drums, use create_drum_track. Only fall back to the manual sequence (create_midi_track → load_instrument_or_effect → set_track_name) when you need custom control between steps.

- **Writing MIDI**: First ensure a clip exists (create_clip or create_clip_with_notes), then write notes with add_notes_to_clip or grid_to_clip. The clip must exist before notes can be written to it.

- **Sound design**: Call get_device_parameters to discover available parameter names and ranges, then use set_device_parameter to adjust individual values. For batch changes, use batch_set_device_parameters.

- **Mixing**: Start with get_full_session_state for a complete overview of all tracks, volumes, pans, sends, and devices. Use batch_set_mixer for multi-track adjustments in a single call rather than individual set_track_volume/set_track_pan calls.

## Prefer Compound Tools

These workflow tools combine multiple operations into a single call, reducing round-trips 3-5x:
- create_instrument_track — track + instrument + name + color
- create_drum_track — MIDI track + Drum Rack + name
- create_clip_with_notes — clip creation + note writing
- batch_set_mixer — volume + pan + send levels for multiple tracks
- apply_effect_chain — load multiple effects from a template
- setup_send_return — creates return track + configures sends

Use these instead of manual multi-step sequences whenever the workflow matches.

## Grid Notation

For drum patterns and rhythmic content, prefer grid_to_clip (ASCII grid notation) over add_notes_to_clip with individual note dictionaries. Grid notation is more compact and readable for patterns. Use clip_to_grid to read existing clips as grids. Grid auto-detects drum vs melodic content.

## M4L Bridge (Optional)

Tools prefixed with m4l_*, plus discover_device_params, snapshot_device_state, restore_device_snapshot, and morph_between_snapshots, require the AbletonBridge Max for Live device to be loaded on any track in the Live set. Check the m4l_connected field from get_server_capabilities:
- If true: full access to hidden parameters, deep device chains, audio analysis, and snapshots.
- If false: use standard get_device_parameters / set_device_parameter instead. These work with all automatable parameters without M4L.

## Input Constraints

- Notes: max 10,000 per add_notes_to_clip call. Split larger writes across multiple calls. Each note requires {pitch, start_time, duration, velocity} — pitch 0-127, velocity 0-127, duration > 0, start_time ≥ 0.
- Automation: max 500 points per call. Points auto-reduce if density exceeds thresholds. Each point requires {time, value} where value is 0.0-1.0 normalized.
- Batch parameters: max 200 per call.
- Batch tracks: max 50 per batch_set_mixer call.
- Time values throughout are in beats (1.0 = one quarter note at current tempo).

## Browser & Loading

load_instrument_or_effect accepts device names directly — "Wavetable", "Operator", "Drift", "Compressor", "EQ Eight", etc. Exact name matching works for all built-in Ableton devices. Use search_browser only when loading user presets, third-party plugins, or items whose exact name is unknown. Browser results return URIs that can be passed to load_browser_item.

## Automation

create_clip_automation writes automation to clip envelopes (Session view). create_track_automation writes to arrangement automation lanes. Both accept a list of {time, value} points. The server automatically reduces point density if too many points are submitted while preserving the curve shape.

## Snapshots

snapshot_device_state captures all device parameters (including hidden ones via M4L) into an in-memory store. morph_between_snapshots interpolates between two saved snapshots at a given ratio. list_snapshots shows all stored snapshots. Snapshots exist in server memory only — they do not persist across server restarts.
""".strip()
