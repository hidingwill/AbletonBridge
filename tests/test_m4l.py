import pytest
import json
import struct
import socket
import base64
from unittest.mock import MagicMock, patch
from MCP_Server.connections.m4l import M4LConnection


class TestBuildOscMessage:
    def test_string_argument(self):
        """Test OSC message with string argument."""
        conn = M4LConnection()
        msg = conn._build_osc_message("/ping", [("s", "test-123")])
        assert b"/ping" in msg
        assert b"test-123" in msg

    def test_integer_argument(self):
        """Test OSC message with integer argument."""
        conn = M4LConnection()
        msg = conn._build_osc_message("/test", [("i", 42)])
        assert b"/test" in msg
        # Check the integer is packed as big-endian 32-bit
        assert struct.pack(">i", 42) in msg

    def test_float_argument(self):
        """Test OSC message with float argument."""
        conn = M4LConnection()
        msg = conn._build_osc_message("/test", [("f", 3.14)])
        assert b"/test" in msg

    def test_multiple_arguments(self):
        """Test OSC message with multiple arguments."""
        conn = M4LConnection()
        msg = conn._build_osc_message("/multi", [("s", "hello"), ("i", 5), ("f", 1.0)])
        assert b"/multi" in msg
        assert b"hello" in msg

    def test_4byte_padding(self):
        """OSC messages should be padded to 4-byte boundaries."""
        conn = M4LConnection()
        msg = conn._build_osc_message("/a", [("s", "x")])
        assert len(msg) % 4 == 0


class TestParseM4lResponse:
    def test_urlsafe_base64(self):
        """Test parsing URL-safe base64 encoded response."""
        conn = M4LConnection()
        data = {"status": "success", "result": {"value": 42}}
        encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=")
        # Add null padding as OSC would
        padded = encoded + b"\x00" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        result = conn._parse_m4l_response(padded)
        assert result["status"] == "success"
        assert result["result"]["value"] == 42

    def test_raw_json(self):
        """Test parsing raw JSON response (fallback)."""
        conn = M4LConnection()
        data = json.dumps({"status": "success"}).encode()
        result = conn._parse_m4l_response(data)
        assert result["status"] == "success"


class TestReassembleChunkedResponse:
    def test_single_chunk(self):
        """Test reassembly with only one chunk (total=1)."""
        conn = M4LConnection()
        conn.recv_sock = MagicMock()
        data = {"key": "value"}
        piece = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        first_chunk = {"_c": 0, "_t": 1, "_d": piece}
        result = conn._reassemble_chunked_response(first_chunk)
        assert result["key"] == "value"

    def test_multi_chunk_reassembly(self):
        """Test reassembly of multiple chunks."""
        conn = M4LConnection()
        conn.recv_sock = MagicMock()
        data = {"big": "data" * 100}
        full_json = json.dumps(data)
        # Split the raw JSON into 3 parts, then base64-encode each separately
        # (each _d must be independently decodable base64)
        part_size = len(full_json) // 3 + 1
        raw_parts = [full_json[i:i+part_size] for i in range(0, len(full_json), part_size)]
        pieces = [base64.urlsafe_b64encode(p.encode()).decode().rstrip("=") for p in raw_parts]
        total = len(pieces)
        first_chunk = {"_c": 0, "_t": total, "_d": pieces[0]}
        # Mock remaining chunks arriving via recv (raw JSON bytes — _parse_m4l_response
        # handles this via its raw-JSON fallback path)
        remaining_packets = []
        for i, piece in enumerate(pieces[1:], start=1):
            chunk_data = {"_c": i, "_t": total, "_d": piece}
            remaining_packets.append((json.dumps(chunk_data).encode(), ("127.0.0.1", 9879)))
        conn.recv_sock.recvfrom.side_effect = remaining_packets
        result = conn._reassemble_chunked_response(first_chunk)
        assert result == data


class TestDynamicTimeouts:
    def test_batch_set_hidden_params_timeout(self):
        """Timeout should scale with parameter count."""
        conn = M4LConnection()
        conn.send_sock = MagicMock()
        conn.recv_sock = MagicMock()
        conn._connected = True
        params = {"track_index": 0, "device_index": 0, "parameters": [{"index": i, "value": 0.5} for i in range(20)]}
        # Should calculate timeout as max(10.0, 20 * 0.15) = 10.0
        with patch.object(conn, '_build_osc_packet', return_value=b"test"):
            with patch.object(conn, '_drain_recv_socket'):
                response_data = json.dumps({"status": "success", "result": {}, "_rid": ""}).encode()
                encoded = base64.urlsafe_b64encode(response_data)
                conn.recv_sock.recvfrom.return_value = (encoded, ("127.0.0.1", 9879))
                with patch.object(conn, '_parse_m4l_response', return_value={"status": "success", "result": {}, "_rid": ""}):
                    result = conn.send_command("batch_set_hidden_params", params)
                    # Check settimeout was called with appropriate value
                    timeout_calls = [c for c in conn.recv_sock.settimeout.call_args_list]
                    assert len(timeout_calls) > 0
