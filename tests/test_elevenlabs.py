"""Tests for MCP_Server/tools/elevenlabs.py — stem naming/order, filenames, client bootstrap, import workflow.

Ableton and ElevenLabs HTTP are mocked. ``SAMPLES_DIR`` is patched to a temp path so tests
never write into the real User Library.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import sys
import time
import types
import zipfile
from unittest.mock import MagicMock, patch

import pytest

import MCP_Server.tools.elevenlabs as el

_PATCH_GAC = "MCP_Server.tools.elevenlabs.get_ableton_connection"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_elevenlabs_singleton():
    el._el_client = None
    yield
    el._el_client = None


def _register_el_tools():
    from mcp.server.fastmcp import FastMCP
    from MCP_Server.tools.elevenlabs import register_tools

    mcp = FastMCP("test-el")
    register_tools(mcp)
    return mcp


def _tool_fn(mcp, name: str):
    return mcp._tool_manager._tools[name].fn


def _stem_zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for stem_name, data in entries:
            zf.writestr(f"{stem_name}.mp3", data)
    return buf.getvalue()


def _inject_minimal_elevenlabs_package():
    """Stub ``elevenlabs.client`` so ``from elevenlabs.client import ElevenLabs`` succeeds."""
    root = types.ModuleType("elevenlabs")
    client_mod = types.ModuleType("elevenlabs.client")
    client_mod.ElevenLabs = MagicMock(name="ElevenLabs")
    sys.modules["elevenlabs"] = root
    sys.modules["elevenlabs.client"] = client_mod
    return client_mod


# ---------------------------------------------------------------------------
# Stem helpers & filename sanitization
# ---------------------------------------------------------------------------


class TestStemSortKey:
    def test_standard_stems_sort_in_mixer_order(self):
        raw = ["vocals", "piano", "drums", "other", "bass", "guitar"]
        sorted_stems = sorted(raw, key=lambda s: el._stem_sort_key(s))
        assert sorted_stems == ["drums", "bass", "guitar", "piano", "other", "vocals"]

    def test_unknown_stem_sorts_after_known(self):
        raw = ["vocals", "xylo", "drums"]
        sorted_stems = sorted(raw, key=lambda s: el._stem_sort_key(s))
        assert sorted_stems == ["drums", "vocals", "xylo"]


class TestStemTrackDisplayName:
    @pytest.mark.parametrize(
        "stem_key,expected",
        [
            ("vocals", "Vocals"),
            ("DRUMS", "Drums"),
            ("instrumental", "Instrumental"),
        ],
    )
    def test_known_keys(self, stem_key, expected):
        assert el._stem_track_display_name(stem_key) == expected

    def test_unknown_key_title_cases(self):
        assert el._stem_track_display_name("custom_stem") == "Custom Stem"


class TestMakeFilename:
    def test_sanitizes_invalid_chars(self):
        name = el._make_filename('foo<>:"/\\|?*bar')
        assert "<" not in name
        assert name.startswith("foobar_")
        assert name.endswith(".mp3")

    def test_empty_after_sanitize_becomes_untitled(self):
        name = el._make_filename("<<<")
        assert name.startswith("untitled_")


# ---------------------------------------------------------------------------
# ElevenLabs client bootstrap
# ---------------------------------------------------------------------------


class TestGetElevenlabsClient:
    def test_raises_when_package_missing(self):
        el._el_client = None
        real_import = builtins.__import__

        def fail_elevenlabs(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "elevenlabs" or name.startswith("elevenlabs."):
                raise ModuleNotFoundError("simulated missing elevenlabs")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fail_elevenlabs):
            with pytest.raises(RuntimeError, match="elevenlabs package not installed"):
                el._get_elevenlabs_client()

    def test_raises_when_api_key_missing(self):
        removed = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            saved = {
                k: sys.modules.pop(k)
                for k in list(sys.modules)
                if k == "elevenlabs" or k.startswith("elevenlabs.")
            }
            try:
                _inject_minimal_elevenlabs_package()
                el._el_client = None
                real_getenv = os.getenv

                def getenv_no_el_key(key, default=None):
                    if key == "ELEVENLABS_API_KEY":
                        return None
                    return real_getenv(key, default)

                with patch.object(el, "os") as mock_os:
                    mock_os.getenv = getenv_no_el_key
                    mock_os.path = os.path
                    mock_os.makedirs = os.makedirs
                    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
                        el._get_elevenlabs_client()
            finally:
                sys.modules.update(saved)
        finally:
            if removed is not None:
                os.environ["ELEVENLABS_API_KEY"] = removed

    def test_builds_client_when_key_present(self):
        saved = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k == "elevenlabs" or k.startswith("elevenlabs.")
        }
        try:
            cm = _inject_minimal_elevenlabs_package()
            el._el_client = None
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "sk-test"}):
                with patch("httpx.Client"):
                    client = el._get_elevenlabs_client()
            cm.ElevenLabs.assert_called_once()
            assert client is not None
        finally:
            sys.modules.update(saved)


# ---------------------------------------------------------------------------
# separate_stems_import_arrangement
# ---------------------------------------------------------------------------


class TestSeparateStemsImportArrangement:
    def test_orders_tracks_and_sets_display_names(self, tmp_path, monkeypatch):
        samples = tmp_path / "Samples"
        samples.mkdir()
        monkeypatch.setattr(el, "SAMPLES_DIR", str(samples))

        mix = samples / "mix.mp3"
        mix.write_bytes(b"fake-mix")

        zip_bytes = _stem_zip_bytes(
            [("vocals", b"v"), ("drums", b"d"), ("bass", b"b")]
        )
        mock_client = MagicMock()
        mock_client.music.separate_stems.return_value = iter([zip_bytes])

        ableton = MagicMock()
        idx = iter(range(20))

        def send(name, args=None):
            if name == "create_audio_track":
                return {"index": next(idx)}
            return {}

        ableton.send_command.side_effect = send

        monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)

        stem_files, track_indices = el.separate_stems_import_arrangement(
            mock_client, str(mix), "MySong", ableton
        )

        assert [s["track_name"] for s in stem_files] == ["Drums", "Bass", "Vocals"]
        assert track_indices == [0, 1, 2]

        set_names = [
            c.args[1]["name"]
            for c in ableton.send_command.call_args_list
            if c.args and c.args[0] == "set_track_name"
        ]
        assert set_names == ["Drums", "Bass", "Vocals"]

    def test_raises_when_zip_has_no_audio(self, tmp_path, monkeypatch):
        samples = tmp_path / "Samples"
        samples.mkdir()
        monkeypatch.setattr(el, "SAMPLES_DIR", str(samples))

        mix = samples / "mix.mp3"
        mix.write_bytes(b"x")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", b"nope")
        zip_bytes = buf.getvalue()

        mock_client = MagicMock()
        mock_client.music.separate_stems.return_value = iter([zip_bytes])

        with pytest.raises(RuntimeError, match="No audio stems"):
            el.separate_stems_import_arrangement(
                mock_client, str(mix), "x", MagicMock()
            )


# ---------------------------------------------------------------------------
# MCP tools (async, mocked API + Ableton)
# ---------------------------------------------------------------------------


class TestGenerateMusicTool:
    @pytest.mark.asyncio
    async def test_auto_import_false_skips_ableton(self, tmp_path, monkeypatch):
        monkeypatch.setattr(el, "SAMPLES_DIR", str(tmp_path))

        mock_client = MagicMock()
        mock_client.music.compose.return_value = iter([b"\x00\x01"])

        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "generate_music")

        with patch("MCP_Server.tools.elevenlabs._get_elevenlabs_client", return_value=mock_client):
            with patch(_PATCH_GAC) as p_gac:
                ctx = MagicMock()
                raw = await fn(
                    ctx,
                    prompt="lofi beat",
                    music_length_ms=3000,
                    auto_import=False,
                )

        p_gac.assert_not_called()
        data = json.loads(raw)
        assert data["status"] == "ok"
        assert "Saved to" in data["message"]

    @pytest.mark.asyncio
    async def test_separate_stems_imports_in_order(self, tmp_path, monkeypatch):
        samples = tmp_path / "Samples"
        samples.mkdir()
        monkeypatch.setattr(el, "SAMPLES_DIR", str(samples))

        zip_bytes = _stem_zip_bytes([("other", b"o"), ("drums", b"d")])
        mock_client = MagicMock()
        mock_client.music.compose.return_value = iter([b"mixdata"])
        mock_client.music.separate_stems.return_value = iter([zip_bytes])

        ableton = MagicMock()
        n = iter(range(10))

        def send(name, args=None):
            if name == "create_audio_track":
                return {"index": next(n)}
            return {}

        ableton.send_command.side_effect = send

        monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)

        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "generate_music")

        with patch("MCP_Server.tools.elevenlabs._get_elevenlabs_client", return_value=mock_client):
            with patch(_PATCH_GAC, return_value=ableton):
                ctx = MagicMock()
                raw = await fn(
                    ctx,
                    prompt="city pop",
                    music_length_ms=3000,
                    separate_stems=True,
                    auto_import=True,
                )

        data = json.loads(raw)
        assert data["status"] == "ok"
        assert data["stem_count"] == 2
        stems = data["stems"]
        assert [s["track_name"] for s in stems] == ["Drums", "Other"]

    @pytest.mark.asyncio
    async def test_validation_empty_prompt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(el, "SAMPLES_DIR", str(tmp_path))
        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "generate_music")

        ctx = MagicMock()
        raw = await fn(ctx, prompt="", music_length_ms=3000)
        data = json.loads(raw)
        assert data["status"] == "error"


class TestSeparateStemsTool:
    @pytest.mark.asyncio
    async def test_missing_file_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(el, "SAMPLES_DIR", str(tmp_path))
        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "separate_stems")

        ctx = MagicMock()
        raw = await fn(ctx, input_file_path="")
        data = json.loads(raw)
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(el, "SAMPLES_DIR", str(tmp_path))
        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "separate_stems")

        missing = tmp_path / "nope.mp3"
        ctx = MagicMock()
        raw = await fn(ctx, input_file_path=str(missing))
        data = json.loads(raw)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_auto_import_false_returns_files_only(self, tmp_path, monkeypatch):
        samples = tmp_path / "Samples"
        samples.mkdir()
        monkeypatch.setattr(el, "SAMPLES_DIR", str(samples))

        src = samples / "source.mp3"
        src.write_bytes(b"src")

        zip_bytes = _stem_zip_bytes([("vocals", b"v")])
        mock_client = MagicMock()
        mock_client.music.separate_stems.return_value = iter([zip_bytes])

        mcp = _register_el_tools()
        fn = _tool_fn(mcp, "separate_stems")

        with patch("MCP_Server.tools.elevenlabs._get_elevenlabs_client", return_value=mock_client):
            with patch(_PATCH_GAC) as p_gac:
                ctx = MagicMock()
                raw = await fn(
                    ctx,
                    input_file_path=str(src),
                    auto_import=False,
                )

        p_gac.assert_not_called()
        data = json.loads(raw)
        assert data["status"] == "ok"
        assert data["stem_count"] == 1
        assert "track_indices" not in data
