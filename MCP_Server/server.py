"""AbletonBridge MCP Server — main entry point.

This is the orchestrator that wires together all modules.
Tool handlers live in MCP_Server/tools/*.py
Connection classes live in MCP_Server/connections/*.py
Cache logic lives in MCP_Server/cache/*.py
Dashboard lives in MCP_Server/dashboard/*.py
All mutable runtime state lives in MCP_Server/state.py
"""

# ---------------------------------------------------------------------------
# Standard library
# ---------------------------------------------------------------------------
import logging
import os
import socket
import sys
import time
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict
from datetime import datetime, timezone
from collections import deque

# ---------------------------------------------------------------------------
# MCP framework
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Internal modules
# ---------------------------------------------------------------------------
import MCP_Server.state as state
from MCP_Server.connections.ableton import AbletonConnection, get_ableton_connection
from MCP_Server.connections.m4l import M4LConnection
from MCP_Server.cache.browser import load_browser_cache_from_disk, populate_browser_cache
from MCP_Server.dashboard.server import (
    start_dashboard_server,
    stop_dashboard_server,
    DashboardLogHandler,
    summarize_args,
)
from MCP_Server.tools import register_all_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AbletonBridge")


# ===================================================================
# Singleton lock — prevent duplicate server instances
# ===================================================================

def _acquire_singleton_lock() -> socket.socket:
    """Acquire an exclusive TCP port lock to prevent duplicate server instances.

    Returns the bound socket (caller must keep it alive for the server's
    lifetime).  Raises RuntimeError if another instance already holds the lock.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", state.SINGLETON_LOCK_PORT))
        sock.listen(1)
        logger.info("Singleton lock acquired on port %d", state.SINGLETON_LOCK_PORT)
        return sock
    except OSError as e:
        sock.close()
        raise RuntimeError(
            f"Another AbletonBridge server instance is already running "
            f"(port {state.SINGLETON_LOCK_PORT} is in use). "
            f"Stop the other instance first."
        ) from e


def _release_singleton_lock(sock: socket.socket):
    """Release the singleton lock by closing the lock socket."""
    if sock:
        try:
            sock.close()
            logger.info("Singleton lock released")
        except Exception:
            pass


# ===================================================================
# M4L auto-connect (background thread)
# ===================================================================

def _m4l_auto_connect():
    """Background thread: create UDP sockets once, retry ping until M4L responds."""
    # Create sockets once — don't tear them down between retries
    conn = M4LConnection()
    if not conn.connect():
        logger.warning("M4L auto-connect: could not bind UDP sockets")
        return

    state.m4l_connection = conn

    # Build a raw OSC ping packet
    ping_id = "autocon"
    ping_osc = M4LConnection._build_osc_message("/ping", [("s", ping_id)])

    for attempt in range(1, 16):  # 15 attempts, ~2 s apart
        try:
            # Drain stale data
            conn._drain_recv_socket()
            conn.recv_sock.settimeout(2.0)

            # Send ping
            conn.send_sock.sendto(ping_osc, (conn.send_host, conn.send_port))

            # Wait for response
            data, _addr = conn.recv_sock.recvfrom(65535)
            result = conn._parse_m4l_response(data)
            if result.get("status") == "success":
                logger.info("M4L bridge auto-connected on attempt %d", attempt)
                state.m4l_ping_cache["result"] = True
                state.m4l_ping_cache["timestamp"] = time.time()
                # Check bridge version compatibility
                M4LConnection._check_bridge_version(result)
                return
        except socket.timeout:
            logger.info(
                "M4L auto-connect %d/15: no response (timeout), retrying...",
                attempt,
            )
        except Exception as e:
            logger.info("M4L auto-connect %d/15: %s", attempt, e)
        time.sleep(2)

    logger.warning(
        "M4L bridge not available after 15 attempts — will retry when needed"
    )


# ===================================================================
# Browser cache warmup (background thread)
# ===================================================================

def _browser_cache_warmup():
    """Background thread: load disk cache instantly, then refresh from Ableton."""
    from MCP_Server.constants import BROWSER_DISK_CACHE_MAX_AGE

    # Step 1: Load from disk (instant, works even before Ableton connects)
    disk_loaded = load_browser_cache_from_disk()
    if disk_loaded:
        age = time.time() - state.browser_cache_timestamp
        if age < BROWSER_DISK_CACHE_MAX_AGE:
            logger.info(
                "Browser cache ready from disk (%.0fs old, skipping rescan)", age
            )
            return
        logger.info(
            "Browser cache loaded from disk (%.0fs old, will refresh)", age
        )

    # Step 2: Wait for Ableton connection, then do a live scan to refresh
    state.ableton_connected_event.wait(timeout=30.0)
    if not (state.ableton_connection and state.ableton_connection.sock):
        logger.warning(
            "Browser cache warmup: Ableton not connected after 30s, skipping live scan"
        )
        return
    time.sleep(0.5)  # brief settle after connection confirmed
    try:
        populate_browser_cache()
    except Exception as e:
        logger.warning("Browser cache warmup failed: %s", e)


# ===================================================================
# Server lifespan — startup / shutdown
# ===================================================================

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    try:
        # Singleton guard
        try:
            state.singleton_lock_sock = _acquire_singleton_lock()
        except RuntimeError as e:
            logger.error(str(e))
            logger.error("Exiting to avoid conflicts.")
            sys.exit(1)

        logger.info("AbletonBridge server starting up")
        state.server_start_time = time.time()

        # Connect to Ableton (Remote Script TCP)
        try:
            ableton = get_ableton_connection()
            logger.info("Successfully connected to Ableton on startup")
        except Exception as e:
            logger.warning("Could not connect to Ableton on startup: %s", e)
            logger.warning("Make sure the Ableton Remote Script is running")

        # Auto-connect M4L bridge in background
        threading.Thread(
            target=_m4l_auto_connect, daemon=True, name="m4l-auto-connect"
        ).start()

        # Start web dashboard on background thread
        try:
            start_dashboard_server()
        except Exception as e:
            logger.warning("Dashboard failed to start: %s", e)

        # Pre-populate browser cache in background
        threading.Thread(
            target=_browser_cache_warmup, daemon=True, name="browser-cache-warmup"
        ).start()

        # Load saved effect chain templates from disk
        try:
            from MCP_Server.tools.workflows import load_chain_templates_from_disk
            load_chain_templates_from_disk()
        except Exception as e:
            logger.warning("Could not load chain templates: %s", e)

        yield {}

    finally:
        # Shutdown sequence
        stop_dashboard_server()

        if state.ableton_connection:
            logger.info("Disconnecting from Ableton on shutdown")
            state.ableton_connection.disconnect()
            state.ableton_connection = None

        if state.m4l_connection:
            logger.info("Disconnecting M4L bridge on shutdown")
            state.m4l_connection.disconnect()
            state.m4l_connection = None

        _release_singleton_lock(state.singleton_lock_sock)
        state.singleton_lock_sock = None
        logger.info("AbletonBridge server shut down")


# ===================================================================
# Create the MCP server instance
# ===================================================================

mcp = FastMCP("AbletonBridge", lifespan=server_lifespan)
state.mcp_instance = mcp


# ===================================================================
# Register all tool modules
# ===================================================================

register_all_tools(mcp)


# ===================================================================
# Register MCP prompts
# ===================================================================

from MCP_Server.prompts import register_prompts
register_prompts(mcp)


# ===================================================================
# MCP Resources — expose live session data via resource URIs
# ===================================================================

@mcp.resource("ableton://session")
def resource_session() -> str:
    """Current Ableton session info (tempo, tracks, transport state)."""
    import json
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_session_info")
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("ableton://tracks")
def resource_tracks() -> str:
    """All track information including devices, clips, and routing."""
    import json
    try:
        ableton = get_ableton_connection()
        result = ableton.send_command("get_all_tracks_info")
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("ableton://capabilities")
def resource_capabilities() -> str:
    """Server capabilities, connection status, and version info."""
    import json
    from MCP_Server import __version__
    result = {
        "server_version": __version__,
        "ableton_connected": bool(state.ableton_connection and state.ableton_connection.sock),
        "m4l_connected": bool(state.m4l_connection and state.m4l_connection._connected),
        "m4l_bridge_version": state.m4l_bridge_version or "unknown",
        "browser_cache_ready": state.browser_cache_ready.is_set(),
        "browser_cache_items": len(state.browser_cache_flat),
    }
    return json.dumps(result)


# ===================================================================
# Tool call instrumentation — captures every tool call for the dashboard
# ===================================================================

_original_call_tool = mcp.call_tool


async def _instrumented_call_tool(name: str, arguments: dict) -> Any:
    """Wrap every tool call to record metrics for the dashboard."""
    start = time.time()
    error_msg = None
    try:
        result = await _original_call_tool(name, arguments)
        return result
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration = time.time() - start
        entry = {
            "tool": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(duration * 1000, 1),
            "error": error_msg,
            "args_summary": summarize_args(arguments),
        }
        with state.tool_call_lock:
            state.tool_call_log.append(entry)
            state.tool_call_counts[name] = state.tool_call_counts.get(name, 0) + 1


mcp.call_tool = _instrumented_call_tool


# ===================================================================
# Dashboard log handler — pipe all log records to the dashboard buffer
# ===================================================================

logging.getLogger().addHandler(DashboardLogHandler())


# ===================================================================
# Entry point
# ===================================================================

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
