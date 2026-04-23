"""ElevenLabs music generation and stem separation tools for AbletonBridge.

Generates music via the ElevenLabs API and imports it directly into Ableton Live.
Requires the 'elevenlabs' optional dependency and ELEVENLABS_API_KEY in .env.
"""

import io
import json
import logging
import os
import pathlib
import re
import zipfile
from datetime import datetime

from mcp.server.fastmcp import Context

from MCP_Server.tools._base import _tool_handler, tool_error
from MCP_Server.connections.ableton import get_ableton_connection

logger = logging.getLogger("AbletonBridge")

SAMPLES_DIR = os.path.join(
    pathlib.Path.home(), "Music", "Ableton", "User Library", "Samples"
)

_el_client = None

# Human-readable Ableton track names + import order (rhythm → harmony → vocals).
STEM_DISPLAY_NAMES = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
    "instrumental": "Instrumental",
}
STEM_IMPORT_ORDER = ("drums", "bass", "guitar", "piano", "other", "vocals", "instrumental")


def _stem_sort_key(stem_key: str) -> tuple[int, str]:
    key = stem_key.lower()
    try:
        return (STEM_IMPORT_ORDER.index(key), key)
    except ValueError:
        return (len(STEM_IMPORT_ORDER), key)


def _stem_track_display_name(stem_key: str) -> str:
    return STEM_DISPLAY_NAMES.get(
        stem_key.lower(),
        stem_key.replace("_", " ").strip().title() or "Stem",
    )


def _get_elevenlabs_client():
    global _el_client
    if _el_client is not None:
        return _el_client

    try:
        from elevenlabs.client import ElevenLabs
    except ImportError:
        raise RuntimeError(
            "elevenlabs package not installed. Run: uv pip install -e \".[elevenlabs]\""
        )

    try:
        from dotenv import load_dotenv
        _repo_root = pathlib.Path(__file__).resolve().parents[2]
        load_dotenv(_repo_root / ".env")
    except ImportError:
        pass

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set. Add it to your .env file."
        )

    import httpx
    http_client = httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0))
    _el_client = ElevenLabs(api_key=api_key, httpx_client=http_client)
    return _el_client


def _make_filename(name: str, ext: str = "mp3") -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name).strip()
    sanitized = re.sub(r'\s+', '_', sanitized)[:60] or "untitled"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{sanitized}_{ts}.{ext}"


def separate_stems_import_arrangement(client, filepath: str, source_name: str, ableton) -> tuple:
    """Separate *filepath* into six stems, save under Samples, import to new tracks (intuitive names + order)."""
    import time as _time

    os.makedirs(SAMPLES_DIR, exist_ok=True)

    logger.info("Separating stems for '%s'", source_name)
    with open(filepath, "rb") as f:
        zip_data = io.BytesIO()
        for chunk in client.music.separate_stems(
            file=f,
            stem_variation_id="six_stems_v1",
            output_format="mp3_44100_128",
        ):
            zip_data.write(chunk)

    zip_data.seek(0)
    stem_files = []

    with zipfile.ZipFile(zip_data, "r") as zf:
        for entry in zf.namelist():
            if not entry.endswith((".mp3", ".wav")):
                continue
            stem_label = pathlib.Path(entry).stem
            stem_filename = _make_filename(f"{source_name}_{stem_label}")
            stem_path = os.path.join(SAMPLES_DIR, stem_filename)

            with open(stem_path, "wb") as out:
                out.write(zf.read(entry))

            stem_files.append({
                "stem": stem_label,
                "filename": stem_filename,
                "filepath": stem_path,
                "file_size_mb": round(os.path.getsize(stem_path) / 1048576, 2),
            })
            logger.info("Extracted stem: %s -> %s", stem_label, stem_path)

    if not stem_files:
        raise RuntimeError("No audio stems found in the response from ElevenLabs")

    _time.sleep(1)

    stem_files.sort(key=lambda s: _stem_sort_key(s["stem"]))

    track_indices = []

    for stem in stem_files:
        track_result = ableton.send_command("create_audio_track", {"index": -1})
        track_idx = track_result.get("index", 0)
        track_indices.append(track_idx)

        track_label = _stem_track_display_name(stem["stem"])
        ableton.send_command("set_track_name", {
            "track_index": track_idx, "name": track_label,
        })

        _time.sleep(0.5)
        ableton.send_command("import_audio_to_arrangement", {
            "track_index": track_idx,
            "file_path": stem["filepath"],
            "position": 0.0,
        })

        stem["track_index"] = track_idx
        stem["track_name"] = track_label

    return stem_files, track_indices


def register_tools(mcp):
    """Register ElevenLabs music generation tools."""

    @mcp.tool()
    @_tool_handler("generating music with ElevenLabs")
    def generate_music(
        ctx: Context,
        prompt: str,
        music_length_ms: int = 30000,
        force_instrumental: bool = False,
        auto_import: bool = True,
        separate_stems: bool = True,
        track_name: str = "",
    ) -> str:
        """Generate music from a text prompt using ElevenLabs AI, separate into stems, and import into Ableton Live.

        By default: generates audio, separates it into 6 stems (vocals, drums, bass,
        guitar, piano, other), and creates a named audio track for each stem in the
        arrangement timeline with full waveform display.

        COST WARNING: This makes API calls to ElevenLabs which cost credits (generation + stem separation).

        Parameters:
        - prompt: Text description of the music (e.g. "upbeat jazz fusion with saxophone")
        - music_length_ms: Duration in milliseconds, 3000-600000. Default 30000 (30s).
        - force_instrumental: If true, no vocals. Default false.
        - auto_import: If true (default), imports into Ableton.
        - separate_stems: If true (default), separates into 6 stems before importing. If false, imports as a single track.
        - track_name: Optional label for saved audio files (mix + stem exports). Stem tracks are named e.g. Vocals, Drums.
        """
        if not prompt:
            raise ValueError("Prompt is required.")
        if music_length_ms < 3000 or music_length_ms > 600000:
            raise ValueError("music_length_ms must be between 3000 (3s) and 600000 (10min)")

        client = _get_elevenlabs_client()
        os.makedirs(SAMPLES_DIR, exist_ok=True)

        display_name = track_name or prompt[:40]
        filename = _make_filename(display_name)
        filepath = os.path.join(SAMPLES_DIR, filename)

        audio_data = client.music.compose(
            prompt=prompt,
            music_length_ms=music_length_ms,
            force_instrumental=force_instrumental,
            output_format="mp3_44100_128",
        )

        with open(filepath, "wb") as f:
            for chunk in audio_data:
                f.write(chunk)

        file_size = os.path.getsize(filepath)
        duration_s = music_length_ms / 1000
        logger.info("ElevenLabs music: %.1fs, %.1fMB -> %s",
                     duration_s, file_size / 1048576, filepath)

        result = {
            "filepath": filepath,
            "filename": filename,
            "duration_s": duration_s,
            "file_size_mb": round(file_size / 1048576, 2),
        }

        if auto_import:
            import time

            ableton = get_ableton_connection()
            source_name = track_name or prompt[:30]

            if separate_stems:
                stem_files, track_indices = separate_stems_import_arrangement(
                    client, filepath, source_name, ableton,
                )
                result.update({
                    "stem_count": len(stem_files),
                    "stems": stem_files,
                    "track_indices": track_indices,
                })
                stem_names = ", ".join(s["track_name"] for s in stem_files)
                return json.dumps({
                    "status": "ok",
                    "message": (
                        f"Generated {duration_s:.0f}s of music, separated into "
                        f"{len(stem_files)} stems, and imported to arrangement: {stem_names}"
                    ),
                    **result,
                })
            else:
                track_result = ableton.send_command("create_audio_track", {"index": -1})
                track_idx = track_result.get("index", 0)

                name = track_name or f"EL Music - {prompt[:30]}"
                ableton.send_command("set_track_name", {
                    "track_index": track_idx, "name": name,
                })

                time.sleep(1)
                ableton.send_command("import_audio_to_arrangement", {
                    "track_index": track_idx,
                    "file_path": filepath,
                    "position": 0.0,
                })

                result.update({
                    "track_index": track_idx,
                    "track_name": name,
                })

                return json.dumps({
                    "status": "ok",
                    "message": f"Generated {duration_s:.0f}s of music and imported to track '{name}' (index {track_idx})",
                    **result,
                })

        return json.dumps({
            "status": "ok",
            "message": f"Generated {duration_s:.0f}s of music. Saved to: {filepath}",
            **result,
        })

    @mcp.tool()
    @_tool_handler("separating stems with ElevenLabs")
    def separate_stems(
        ctx: Context,
        input_file_path: str,
        stem_mode: str = "six",
        auto_import: bool = True,
        group_name: str = "",
    ) -> str:
        """Separate an audio file into individual stems (drums, bass, vocals, etc.) using ElevenLabs AI.

        Takes an audio file, sends it to ElevenLabs for stem separation, saves each
        stem as a separate MP3, and optionally creates Ableton tracks for each stem.

        COST WARNING: This makes an API call to ElevenLabs which costs credits.

        Parameters:
        - input_file_path: Path to the audio file to separate (MP3, WAV, etc.)
        - stem_mode: "six" for 6 stems (vocals, drums, bass, guitar, piano, other) or "two" for 2 stems (vocals, instrumental). Default "six".
        - auto_import: If true (default), creates Ableton tracks for each stem with samples loaded.
        - group_name: Optional label for exported stem filenames. Tracks are named e.g. Vocals, Drums.
        """
        if not input_file_path:
            raise ValueError("input_file_path is required.")

        filepath = pathlib.Path(input_file_path).expanduser()
        if not filepath.exists():
            raise ValueError(f"File not found: {filepath}")

        client = _get_elevenlabs_client()
        os.makedirs(SAMPLES_DIR, exist_ok=True)

        variation = "six_stems_v1" if stem_mode == "six" else "two_stems_v1"
        source_name = group_name or filepath.stem

        logger.info("Separating stems for '%s' using %s", filepath.name, variation)

        with open(filepath, "rb") as f:
            zip_data = io.BytesIO()
            for chunk in client.music.separate_stems(
                file=f,
                stem_variation_id=variation,
                output_format="mp3_44100_128",
            ):
                zip_data.write(chunk)

        zip_data.seek(0)
        stem_files = []

        with zipfile.ZipFile(zip_data, "r") as zf:
            for entry in zf.namelist():
                if not entry.endswith((".mp3", ".wav")):
                    continue
                stem_label = pathlib.Path(entry).stem
                stem_filename = _make_filename(f"{source_name}_{stem_label}")
                stem_path = os.path.join(SAMPLES_DIR, stem_filename)

                with open(stem_path, "wb") as out:
                    out.write(zf.read(entry))

                stem_files.append({
                    "stem": stem_label,
                    "filename": stem_filename,
                    "filepath": stem_path,
                    "file_size_mb": round(os.path.getsize(stem_path) / 1048576, 2),
                })
                logger.info("Extracted stem: %s -> %s", stem_label, stem_path)

        if not stem_files:
            raise RuntimeError("No audio stems found in the response from ElevenLabs")

        result = {
            "source_file": str(filepath),
            "stem_mode": stem_mode,
            "stem_count": len(stem_files),
            "stems": stem_files,
        }

        if auto_import:
            import time
            ableton = get_ableton_connection()
            time.sleep(1)

            stem_files.sort(key=lambda s: _stem_sort_key(s["stem"]))

            track_indices = []
            for stem in stem_files:
                track_result = ableton.send_command("create_audio_track", {"index": -1})
                track_idx = track_result.get("index", 0)
                track_indices.append(track_idx)

                track_label = _stem_track_display_name(stem["stem"])
                ableton.send_command("set_track_name", {
                    "track_index": track_idx, "name": track_label,
                })

                time.sleep(1)
                ableton.send_command("import_audio_to_arrangement", {
                    "track_index": track_idx,
                    "file_path": stem["filepath"],
                    "position": 0.0,
                })

                stem["track_index"] = track_idx
                stem["track_name"] = track_label

            result["track_indices"] = track_indices
            return json.dumps({
                "status": "ok",
                "message": f"Separated '{source_name}' into {len(stem_files)} stems as audio clips on tracks {track_indices}",
                **result,
            })

        return json.dumps({
            "status": "ok",
            "message": f"Separated '{source_name}' into {len(stem_files)} stems. Files saved to {SAMPLES_DIR}",
            **result,
        })
