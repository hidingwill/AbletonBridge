from MCP_Server.constants import (
    TIER_0_COMMANDS, TIER_1_COMMANDS, TIER_2_COMMANDS, MODIFYING_COMMANDS,
)


class TestCommandTiers:
    def test_tiers_are_disjoint(self):
        """No command should appear in multiple tiers."""
        assert TIER_0_COMMANDS.isdisjoint(TIER_1_COMMANDS)
        assert TIER_0_COMMANDS.isdisjoint(TIER_2_COMMANDS)
        assert TIER_1_COMMANDS.isdisjoint(TIER_2_COMMANDS)

    def test_modifying_is_union(self):
        """MODIFYING_COMMANDS should be the union of all three tiers."""
        assert MODIFYING_COMMANDS == TIER_0_COMMANDS | TIER_1_COMMANDS | TIER_2_COMMANDS

    def test_tiers_are_not_empty(self):
        assert len(TIER_0_COMMANDS) > 0
        assert len(TIER_1_COMMANDS) > 0
        assert len(TIER_2_COMMANDS) > 0

    def test_common_commands_in_correct_tier(self):
        """Spot-check that important commands are in the right tier."""
        assert "set_tempo" in TIER_0_COMMANDS
        assert "set_track_volume" in TIER_0_COMMANDS
        assert "add_notes_to_clip" in TIER_1_COMMANDS
        assert "create_midi_track" in TIER_2_COMMANDS
        assert "load_instrument_or_effect" in TIER_2_COMMANDS
