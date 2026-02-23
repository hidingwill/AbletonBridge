"""AbletonConnection — TCP socket connection to the Ableton Remote Script."""

import socket
import json
import logging
import time
import threading
from dataclasses import dataclass
from typing import Dict, Any

from MCP_Server.constants import TIER_0_COMMANDS, TIER_1_COMMANDS, TIER_2_COMMANDS, MODIFYING_COMMANDS
import MCP_Server.state as state

logger = logging.getLogger("AbletonBridge")

# Phase 4.5: Non-idempotent commands should NOT be retried automatically
# because a retry could create duplicate tracks, clips, etc.
NON_IDEMPOTENT_COMMANDS = frozenset([
    "create_midi_track", "create_audio_track", "create_clip",
    "create_return_track", "create_scene", "delete_track",
    "delete_clip", "delete_scene", "delete_device",
    "duplicate_track", "duplicate_clip", "add_notes_to_clip",
    "add_notes_extended", "delete_return_track",
])


@dataclass
class AbletonConnection:
    host: str
    port: int
    sock: socket.socket = None
    _udp_sock: socket.socket = None
    _udp_port: int = 9882

    def connect(self) -> bool:
        """Connect to the Ableton Remote Script socket server"""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self._recv_buffer = ""  # Clear buffer on new connection
            logger.info("Connected to Ableton at %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect to Ableton: %s", e)
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            return False

    def disconnect(self):
        """Disconnect from the Ableton Remote Script"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error("Error disconnecting from Ableton: %s", e)
            finally:
                self.sock = None
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            finally:
                self._udp_sock = None

    def __post_init__(self):
        self._recv_buffer = ""

    def _ensure_udp_socket(self):
        """Create a UDP socket for real-time parameter sending if not already open."""
        if self._udp_sock is None:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._udp_sock

    def send_udp_command(self, command_type: str, params: Dict[str, Any] = None):
        """Send a fire-and-forget UDP command to the Remote Script.

        No response is expected or waited for.
        """
        sock = self._ensure_udp_socket()
        command = {
            "type": command_type,
            "params": params or {}
        }
        payload = json.dumps(command).encode("utf-8")
        sock.sendto(payload, (self.host, self._udp_port))
        logger.debug("Sent UDP command: %s", command_type)

    def receive_full_response(self, sock, buffer_size=8192, timeout=15.0):
        """Receive a complete newline-delimited JSON response and return the parsed object"""
        sock.settimeout(timeout)

        try:
            while True:
                # Check if we already have a complete line in the buffer
                if '\n' in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        result = json.loads(line)
                        logger.debug("Received complete response (%d chars)", len(line))
                        return result

                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        raise Exception("Connection closed before receiving any data")

                    self._recv_buffer += chunk.decode('utf-8')
                except socket.timeout:
                    logger.warning("Socket timeout during receive")
                    raise
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error("Socket connection error during receive: %s", e)
                    raise
        except (socket.timeout, json.JSONDecodeError):
            raise
        except Exception as e:
            logger.error("Error during receive: %s", e)
            raise

    def _reconnect(self) -> bool:
        """Force a fresh reconnection, clearing all state."""
        logger.info("Forcing reconnection to Ableton...")
        self.disconnect()
        self._recv_buffer = ""
        return self.connect()

    def send_command(self, command_type: str, params: Dict[str, Any] = None, timeout: float = None) -> Dict[str, Any]:
        """Send a command to Ableton and return the response.

        Includes automatic retry: if the first attempt fails due to a
        socket error, the connection is reset and the command is retried once.
        Adds small delays around modifying commands for stability.

        Non-idempotent commands (create/delete operations) are NOT retried
        to prevent duplicate side-effects (Phase 4.5).
        """
        # Phase 4.5: non-idempotent commands get a single attempt
        max_attempts = 1 if command_type in NON_IDEMPOTENT_COMMANDS else 2
        is_modifying = command_type in MODIFYING_COMMANDS

        # Determine delay tier: Tier 0 = no delay, Tier 1 = 50ms post, Tier 2 = 100ms pre+post
        if command_type in TIER_2_COMMANDS:
            pre_delay, post_delay = 0.1, 0.1
        elif command_type in TIER_1_COMMANDS:
            pre_delay, post_delay = 0, 0.05
        else:
            pre_delay, post_delay = 0, 0

        for attempt in range(1, max_attempts + 1):
            if not self.sock and not self.connect():
                raise ConnectionError("Not connected to Ableton")

            command = {
                "type": command_type,
                "params": params or {}
            }

            try:
                logger.debug("Sending command: %s (attempt %d)", command_type, attempt)

                # Send the command as newline-delimited JSON
                self.sock.sendall((json.dumps(command) + '\n').encode('utf-8'))

                # Pre-delay: give Ableton time to process before we read the response
                if pre_delay:
                    time.sleep(pre_delay)

                # Set timeout based on command type (caller override takes priority)
                if timeout is None:
                    timeout = 15.0 if is_modifying else 10.0
                # Receive the response (already parsed by receive_full_response)
                response = self.receive_full_response(self.sock, timeout=timeout)
                logger.debug("Response status: %s", response.get('status', 'unknown'))

                if response.get("status") == "error":
                    logger.error("Ableton error: %s", response.get('message'))
                    raise Exception(response.get("message", "Unknown error from Ableton"))

                # Post-delay: let Ableton settle before the next command
                if post_delay:
                    time.sleep(post_delay)

                return response.get("result", {})

            except Exception as e:
                logger.error("Command '%s' attempt %d failed: %s", command_type, attempt, e)
                # Close the broken socket and clear buffer
                self.disconnect()
                self._recv_buffer = ""

                if attempt < max_attempts:
                    # Wait briefly then retry with a fresh connection
                    time.sleep(0.3)
                    if not self.connect():
                        raise ConnectionError("Failed to reconnect to Ableton")
                    logger.info("Reconnected, retrying command...")
                else:
                    raise Exception(f"Command '{command_type}' failed after {max_attempts} attempts: {e}")


def get_ableton_connection():
    """Get or create a persistent Ableton connection"""

    if state.ableton_connection is not None:
        try:
            # Test if the socket is still connected
            if state.ableton_connection.sock is None:
                raise ConnectionError("Socket is None")
            state.ableton_connection.sock.settimeout(1.0)
            state.ableton_connection.sock.getpeername()  # raises if disconnected
            return state.ableton_connection
        except Exception as e:
            logger.warning("Existing connection is no longer valid: %s", e)
            try:
                state.ableton_connection.disconnect()
            except Exception:
                pass
            state.ableton_connection = None

    # Connection doesn't exist or is invalid, create a new one
    if state.ableton_connection is None:
        # Try to connect up to 3 times with a short delay between attempts
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info("Connecting to Ableton (attempt %d/%d)...", attempt, max_attempts)
                state.ableton_connection = AbletonConnection(host="localhost", port=9877)
                if state.ableton_connection.connect():
                    logger.info("Created new persistent connection to Ableton")

                    # Validate connection with a simple command
                    try:
                        # Get session info as a test
                        state.ableton_connection.send_command("get_session_info")
                        logger.info("Connection validated successfully")
                        state.ableton_connected_event.set()
                        return state.ableton_connection
                    except Exception as e:
                        logger.error("Connection validation failed: %s", e)
                        state.ableton_connection.disconnect()
                        state.ableton_connection = None
                        # Continue to next attempt
                else:
                    state.ableton_connection = None
            except Exception as e:
                logger.error("Connection attempt %d failed: %s", attempt, e)
                if state.ableton_connection:
                    state.ableton_connection.disconnect()
                    state.ableton_connection = None

            # Wait before trying again, but only if we have more attempts left
            if attempt < max_attempts:
                time.sleep(1.0)

        # If we get here, all connection attempts failed
        if state.ableton_connection is None:
            logger.error("Failed to connect to Ableton after multiple attempts")
            raise Exception("Could not connect to Ableton. Make sure the Remote Script is running.")

    return state.ableton_connection
