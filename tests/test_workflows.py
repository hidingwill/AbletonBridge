"""Tests for MCP_Server/tools/workflows.py -- compound workflow tools.

These high-level tools orchestrate multiple Remote Script commands in a single
MCP tool call.  Tests verify the correct command sequence, error accumulation
behaviour, and round-trip logic for template save/load.

All Ableton / M4L connections are mocked via conftest.py fixtures
(patch_ableton, reset_state).  Because workflows.py binds
``get_ableton_connection`` at import time via ``from ... import``, each test
also patches the module-level name so the tool closures use the per-test mock.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call
import MCP_Server.state as state

# Module path for the import-time binding of get_ableton_connection
_PATCH_GAC = 'MCP_Server.tools.workflows.get_ableton_connection'
_PATCH_URI = 'MCP_Server.tools.workflows.resolve_device_uri'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_workflow_tools():
    """Create a disposable FastMCP instance with workflow tools registered."""
    from mcp.server.fastmcp import FastMCP
    from MCP_Server.tools.workflows import register_tools
    mcp = FastMCP("test")
    register_tools(mcp)
    return mcp


def _get_tool(mcp, name):
    """Retrieve a registered tool function by name."""
    tools = mcp._tool_manager._tools
    tool_fn = tools.get(name)
    assert tool_fn is not None, f"Tool '{name}' was not registered"
    return tool_fn


# ---------------------------------------------------------------------------
# create_instrument_track
# ---------------------------------------------------------------------------

class TestCreateInstrumentTrack:

    @pytest.mark.asyncio
    async def test_basic_creation(self, patch_ableton):
        """Should create track, load instrument, set name, and return JSON."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_instrument_track")

            patch_ableton.send_command.return_value = {"status": "success", "index": 3}

            with patch(_PATCH_URI, return_value="query:Instruments#Wavetable"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, instrument_name="Wavetable",
                                          track_name="My Synth")

            data = json.loads(result)
            assert data["track_index"] == 3
            assert data["instrument"] == "Wavetable"
            assert data["name"] == "My Synth"

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert cmd_names[0] == "create_midi_track"
            assert "load_instrument_or_effect" in cmd_names
            assert "set_track_name" in cmd_names

    @pytest.mark.asyncio
    async def test_default_track_name_uses_instrument(self, patch_ableton):
        """When track_name is empty, the instrument name should be used."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_instrument_track")

            patch_ableton.send_command.return_value = {"status": "success", "index": 0}

            with patch(_PATCH_URI, return_value="query:Instruments#Drift"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, instrument_name="Drift")

            data = json.loads(result)
            assert data["name"] == "Drift"

    @pytest.mark.asyncio
    async def test_color_index_sets_color(self, patch_ableton):
        """Positive color_index should trigger set_track_color command."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_instrument_track")

            patch_ableton.send_command.return_value = {"status": "success", "index": 1}

            with patch(_PATCH_URI, return_value="query:Instruments#Operator"):
                ctx = MagicMock()
                await tool_fn.fn(ctx, instrument_name="Operator", color_index=5)

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "set_track_color" in cmd_names

    @pytest.mark.asyncio
    async def test_no_color_when_minus_one(self, patch_ableton):
        """color_index=-1 (default) should skip set_track_color."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_instrument_track")

            patch_ableton.send_command.return_value = {"status": "success", "index": 0}

            with patch(_PATCH_URI, return_value="query:Instruments#Wavetable"):
                ctx = MagicMock()
                await tool_fn.fn(ctx, instrument_name="Wavetable", color_index=-1)

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "set_track_color" not in cmd_names


# ---------------------------------------------------------------------------
# create_clip_with_notes
# ---------------------------------------------------------------------------

class TestCreateClipWithNotes:

    @pytest.mark.asyncio
    async def test_creates_clip_and_adds_notes(self, patch_ableton):
        """Should call create_clip then add_notes_to_clip."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_clip_with_notes")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            notes = [
                {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
                {"pitch": 64, "start_time": 1.0, "duration": 1.0, "velocity": 90},
            ]
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      length=4.0, notes=notes, clip_name="Test Clip")

            data = json.loads(result)
            assert data["note_count"] == 2
            assert data["length"] == 4.0
            assert data["name"] == "Test Clip"

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert cmd_names[0] == "create_clip"
            assert "add_notes_to_clip" in cmd_names
            assert "set_clip_name" in cmd_names

    @pytest.mark.asyncio
    async def test_no_clip_name_skips_set_name(self, patch_ableton):
        """Empty clip_name should skip the set_clip_name call."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_clip_with_notes")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            notes = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}]
            await tool_fn.fn(ctx, track_index=0, clip_index=0,
                             length=2.0, notes=notes, clip_name="")

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "set_clip_name" not in cmd_names

    @pytest.mark.asyncio
    async def test_invalid_length_rejected(self, patch_ableton):
        """Non-positive length should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_clip_with_notes")

            ctx = MagicMock()
            notes = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}]
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      length=-1.0, notes=notes)
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_empty_notes_rejected(self, patch_ableton):
        """Empty notes list should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_clip_with_notes")

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, track_index=0, clip_index=0,
                                      length=4.0, notes=[])
            assert "Invalid input" in result


# ---------------------------------------------------------------------------
# batch_set_mixer
# ---------------------------------------------------------------------------

class TestBatchSetMixer:

    @pytest.mark.asyncio
    async def test_multiple_tracks(self, patch_ableton):
        """Should process multiple track settings and report totals."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            settings = [
                {"track_index": 0, "volume": 0.8, "pan": -0.5},
                {"track_index": 1, "mute": True},
            ]
            result = await tool_fn.fn(ctx, settings=settings)

            data = json.loads(result)
            assert data["settings_processed"] == 2
            assert data["params_applied"] >= 3  # volume + pan + mute

    @pytest.mark.asyncio
    async def test_error_accumulation(self, patch_ableton):
        """Errors on individual tracks should not stop processing others."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            def side_effect(cmd, params=None):
                if params and params.get("track_index") == 0:
                    raise Exception("Track 0 error")
                return {"status": "success"}
            patch_ableton.send_command.side_effect = side_effect

            ctx = MagicMock()
            settings = [
                {"track_index": 0, "volume": 0.8},
                {"track_index": 1, "volume": 0.6},
            ]
            result = await tool_fn.fn(ctx, settings=settings)

            data = json.loads(result)
            assert len(data["errors"]) >= 1
            assert data["params_applied"] >= 1  # track 1 should succeed

    @pytest.mark.asyncio
    async def test_missing_track_index_error(self, patch_ableton):
        """Settings without track_index should produce an error entry."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            settings = [
                {"volume": 0.8},  # missing track_index
                {"track_index": 1, "volume": 0.6},
            ]
            result = await tool_fn.fn(ctx, settings=settings)

            data = json.loads(result)
            assert len(data["errors"]) >= 1
            assert any("missing track_index" in e["error"] for e in data["errors"])

    @pytest.mark.asyncio
    async def test_empty_settings_rejected(self, patch_ableton):
        """Empty settings list should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, settings=[])
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_solo_param_applied(self, patch_ableton):
        """Solo parameter should trigger set_track_solo command."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            settings = [{"track_index": 2, "solo": True}]
            result = await tool_fn.fn(ctx, settings=settings)

            data = json.loads(result)
            assert data["params_applied"] == 1

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "set_track_solo" in cmd_names

    @pytest.mark.asyncio
    async def test_return_track_type(self, patch_ableton):
        """track_type='return' should use return-specific commands."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "batch_set_mixer")

            patch_ableton.send_command.return_value = {"status": "success"}

            ctx = MagicMock()
            settings = [{"track_index": 0, "track_type": "return", "volume": 0.7}]
            result = await tool_fn.fn(ctx, settings=settings)

            data = json.loads(result)
            assert data["params_applied"] == 1

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "set_return_track_volume" in cmd_names


# ---------------------------------------------------------------------------
# apply_effect_chain
# ---------------------------------------------------------------------------

class TestApplyEffectChain:

    @pytest.mark.asyncio
    async def test_loads_multiple_effects(self, patch_ableton):
        """Should load each effect in order."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "apply_effect_chain")

            patch_ableton.send_command.return_value = {"status": "success"}

            with patch(_PATCH_URI,
                        side_effect=lambda name: f"query:Audio Effects#{name}"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, track_index=0,
                                          effects=["EQ Eight", "Compressor", "Limiter"])

            data = json.loads(result)
            assert len(data["loaded"]) == 3
            assert len(data["failed"]) == 0

    @pytest.mark.asyncio
    async def test_partial_failure(self, patch_ableton):
        """If one effect fails to load, others should still succeed."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "apply_effect_chain")

            call_count = [0]
            def cmd_handler(cmd, params=None):
                if cmd == "load_instrument_or_effect":
                    call_count[0] += 1
                    if call_count[0] == 2:
                        raise Exception("Device not found")
                return {"status": "success"}
            patch_ableton.send_command.side_effect = cmd_handler

            with patch(_PATCH_URI,
                        side_effect=lambda name: f"query:Audio Effects#{name}"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, track_index=0,
                                          effects=["EQ Eight", "MissingPlugin", "Limiter"])

            data = json.loads(result)
            assert len(data["loaded"]) == 2
            assert len(data["failed"]) == 1

    @pytest.mark.asyncio
    async def test_empty_effects_rejected(self, patch_ableton):
        """Empty effects list should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "apply_effect_chain")

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, track_index=0, effects=[])
            assert "Invalid input" in result


# ---------------------------------------------------------------------------
# save_effect_chain / load_effect_chain round-trip
# ---------------------------------------------------------------------------

class TestEffectChainRoundTrip:

    @pytest.mark.asyncio
    async def test_save_and_load(self, patch_ableton):
        """Save + load should round-trip through effect_chain_store."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()

            # Mock getting track info with devices
            def cmd_handler(cmd, params=None):
                if cmd == "get_track_info":
                    return {
                        "devices": [
                            {"name": "EQ Eight", "class_name": "Eq8"},
                            {"name": "Compressor", "class_name": "Compressor"},
                        ]
                    }
                if cmd == "get_device_parameters":
                    return {"parameters": [{"name": "Gain", "value": 0.5}]}
                return {"status": "success", "index": 0}
            patch_ableton.send_command.side_effect = cmd_handler

            ctx = MagicMock()

            # Save the chain
            save_fn = _get_tool(mcp, "save_effect_chain")
            result = await save_fn.fn(ctx, track_index=0, template_name="my_chain")
            data = json.loads(result)
            assert data["device_count"] == 2
            assert data["template_name"] == "my_chain"

            # Verify in store
            assert "my_chain" in state.effect_chain_store
            template = state.effect_chain_store["my_chain"]
            assert len(template["devices"]) == 2
            assert template["devices"][0]["name"] == "EQ Eight"

            # Load the chain onto a different track
            load_fn = _get_tool(mcp, "load_effect_chain")
            patch_ableton.send_command.reset_mock()
            patch_ableton.send_command.side_effect = None
            patch_ableton.send_command.return_value = {"status": "success"}

            with patch(_PATCH_URI,
                        side_effect=lambda name: f"query:Audio Effects#{name}"):
                result = await load_fn.fn(ctx, track_index=1,
                                          template_name="my_chain")

            data = json.loads(result)
            assert len(data["loaded"]) == 2
            assert data["loaded"][0] == "EQ Eight"
            assert data["loaded"][1] == "Compressor"

    @pytest.mark.asyncio
    async def test_load_nonexistent_template(self, patch_ableton):
        """Loading a template that does not exist should return Invalid input."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()

            load_fn = _get_tool(mcp, "load_effect_chain")
            ctx = MagicMock()
            result = await load_fn.fn(ctx, track_index=0,
                                      template_name="no_such_template")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_save_empty_name_rejected(self, patch_ableton):
        """Empty template name should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()

            save_fn = _get_tool(mcp, "save_effect_chain")
            ctx = MagicMock()
            result = await save_fn.fn(ctx, track_index=0, template_name="   ")
            assert "Invalid input" in result

    @pytest.mark.asyncio
    async def test_list_effect_chain_templates(self, patch_ableton):
        """list_effect_chain_templates should reflect saved templates."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()

            # Manually add a template to state
            state.effect_chain_store["preset_a"] = {
                "name": "preset_a",
                "devices": [{"name": "Reverb"}],
                "source_track_type": "track",
            }

            list_fn = _get_tool(mcp, "list_effect_chain_templates")
            ctx = MagicMock()
            result = await list_fn.fn(ctx)

            data = json.loads(result)
            names = [t["name"] for t in data["templates"]]
            assert "preset_a" in names


# ---------------------------------------------------------------------------
# get_full_session_state
# ---------------------------------------------------------------------------

class TestGetFullSessionState:

    @pytest.mark.asyncio
    async def test_aggregates_four_commands(self, patch_ableton):
        """Should aggregate session + tracks + returns + scenes into one response."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "get_full_session_state")

            call_count = [0]
            def cmd_handler(cmd, params=None):
                call_count[0] += 1
                responses = {
                    "get_session_info": {"tempo": 120, "time_signature": "4/4"},
                    "get_all_tracks_info": {"tracks": [{"name": "Track 1"}]},
                    "get_return_tracks": {"tracks": []},
                    "get_scenes": {"scenes": [{"name": "Scene 1"}]},
                }
                return responses.get(cmd, {"status": "success"})
            patch_ableton.send_command.side_effect = cmd_handler

            ctx = MagicMock()
            result = await tool_fn.fn(ctx)

            data = json.loads(result)
            assert data["session"]["tempo"] == 120
            assert len(data["tracks"]["tracks"]) == 1
            assert len(data["scenes"]["scenes"]) == 1
            assert call_count[0] == 4


# ---------------------------------------------------------------------------
# setup_send_return
# ---------------------------------------------------------------------------

class TestSetupSendReturn:

    @pytest.mark.asyncio
    async def test_creates_return_with_effect(self, patch_ableton):
        """Should create return track, load effect, set name."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "setup_send_return")

            def cmd_handler(cmd, params=None):
                if cmd == "create_return_track":
                    return {"index": 0}
                if cmd == "get_return_tracks":
                    return {"tracks": [{"name": "Return A"}]}
                return {"status": "success"}
            patch_ableton.send_command.side_effect = cmd_handler

            with patch(_PATCH_URI, return_value="query:Audio Effects#Reverb"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, effect_name="Reverb",
                                          return_name="Rev Bus")

            data = json.loads(result)
            assert data["return_index"] == 0
            assert data["effect"] == "Reverb"
            assert data["name"] == "Rev Bus"

    @pytest.mark.asyncio
    async def test_sets_sends_on_source_tracks(self, patch_ableton):
        """Providing source_tracks should trigger set_track_send calls."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "setup_send_return")

            def cmd_handler(cmd, params=None):
                if cmd == "create_return_track":
                    return {"index": 1}
                if cmd == "get_return_tracks":
                    return {"tracks": [{"name": "A"}, {"name": "B"}]}
                return {"status": "success"}
            patch_ableton.send_command.side_effect = cmd_handler

            with patch(_PATCH_URI, return_value="query:Audio Effects#Delay"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, effect_name="Delay",
                                          source_tracks=[0, 1, 2],
                                          send_level=0.7)

            data = json.loads(result)
            assert data["sends_set"] == 3

            send_calls = [c for c in patch_ableton.send_command.call_args_list
                          if c[0][0] == "set_track_send"]
            assert len(send_calls) == 3


# ---------------------------------------------------------------------------
# create_drum_track (compound workflow)
# ---------------------------------------------------------------------------

class TestCreateDrumTrack:

    @pytest.mark.asyncio
    async def test_full_drum_track_creation(self, patch_ableton):
        """Should create track, load Drum Rack, create clip, and add notes."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_drum_track")

            patch_ableton.send_command.return_value = {"status": "success", "index": 5}

            with patch(_PATCH_URI, return_value="query:Instruments#Drum Rack"):
                ctx = MagicMock()
                result = await tool_fn.fn(ctx, pattern_style="house",
                                          name="House Drums", clip_length=4.0)

            data = json.loads(result)
            assert data["track_index"] == 5
            assert data["pattern_style"] == "house"
            assert data["note_count"] > 0

            cmd_names = [c[0][0] for c in patch_ableton.send_command.call_args_list]
            assert "create_midi_track" in cmd_names
            assert "load_instrument_or_effect" in cmd_names
            assert "create_clip" in cmd_names
            assert "add_notes_to_clip" in cmd_names

    @pytest.mark.asyncio
    async def test_invalid_pattern_style_rejected(self, patch_ableton):
        """Unknown pattern_style should return Invalid input error."""
        with patch(_PATCH_GAC, return_value=patch_ableton):
            mcp = _register_workflow_tools()
            tool_fn = _get_tool(mcp, "create_drum_track")

            ctx = MagicMock()
            result = await tool_fn.fn(ctx, pattern_style="breakcore")
            assert "Invalid input" in result
