"""Tool registration for AbletonBridge MCP server."""
from . import (
    session, tracks, clips, devices, browser, mixer,
    automation, arrangement, creative, m4l_tools,
    snapshots, audio, grid, workflows,
)


def register_all_tools(mcp):
    """Register all tool modules with the MCP server instance."""
    session.register_tools(mcp)
    tracks.register_tools(mcp)
    clips.register_tools(mcp)
    devices.register_tools(mcp)
    browser.register_tools(mcp)
    mixer.register_tools(mcp)
    automation.register_tools(mcp)
    arrangement.register_tools(mcp)
    creative.register_tools(mcp)
    m4l_tools.register_tools(mcp)
    snapshots.register_tools(mcp)
    audio.register_tools(mcp)
    grid.register_tools(mcp)
    workflows.register_tools(mcp)
