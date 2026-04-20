"""Arrangement tool handlers for AbletonBridge."""
import json
import logging
import math
from typing import Optional
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _report_progress
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.validation import _validate_index, _validate_range

logger = logging.getLogger("AbletonBridge")


def register_tools(mcp):
    @mcp.tool()
    @_tool_handler("getting arrangement clips")
    def get_arrangement_clips(ctx: Context, track_index: int) -> str:
        """Get all clips in arrangement view for a track.

        Parameters:
        - track_index: The index of the track to get arrangement clips from
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_arrangement_clips", {"track_index": track_index})
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("deleting time")
    def delete_time(ctx: Context, start_time: float, end_time: float) -> str:
        """Delete a section of time from the arrangement (removes time and shifts everything after).

        Parameters:
        - start_time: Start position in beats
        - end_time: End position in beats
        """
        if start_time >= end_time:
            return "Error: start_time must be less than end_time"
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_time", {
            "start_time": start_time,
            "end_time": end_time,
        })
        return f"Deleted time from {start_time} to {end_time} ({result.get('deleted_length', end_time - start_time)} beats)"

    @mcp.tool()
    @_tool_handler("duplicating time")
    def duplicate_time(ctx: Context, start_time: float, end_time: float) -> str:
        """Duplicate a section of time in the arrangement (copies and inserts after the selection).

        Parameters:
        - start_time: Start position in beats
        - end_time: End position in beats
        """
        if start_time >= end_time:
            return "Error: start_time must be less than end_time"
        ableton = get_ableton_connection()
        result = ableton.send_command("duplicate_time", {
            "start_time": start_time,
            "end_time": end_time,
        })
        return f"Duplicated time from {start_time} to {end_time} (pasted at {result.get('pasted_at', end_time)})"

    @mcp.tool()
    @_tool_handler("inserting silence")
    def insert_silence(ctx: Context, position: float, length: float) -> str:
        """Insert silence at a position in the arrangement (shifts everything after).

        Parameters:
        - position: The position in beats to insert silence at
        - length: The length of silence in beats
        """
        if length <= 0:
            return "Error: length must be greater than 0"
        ableton = get_ableton_connection()
        result = ableton.send_command("insert_silence", {
            "position": position,
            "length": length,
        })
        return f"Inserted {length} beats of silence at position {position}"

    @mcp.tool()
    @_tool_handler("creating arrangement MIDI clip")
    def create_arrangement_midi_clip(ctx: Context, track_index: int, time: float, length: float) -> str:
        """Create a new MIDI clip in the arrangement view at a specific time position.

        Requires Live 12.1+ and a MIDI track.

        Parameters:
        - track_index: The index of the MIDI track
        - time: Start time in beats for the new clip
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_arrangement_midi_clip", {
            "track_index": track_index,
            "time": time,
            "length": length,
        })
        return f"Created arrangement MIDI clip on track {track_index} at beat {time}, length {length}"

    @mcp.tool()
    @_tool_handler("creating arrangement audio clip")
    def create_arrangement_audio_clip(ctx: Context, track_index: int, time: float, length: float) -> str:
        """Create a new audio clip in the arrangement view at a specific time position.

        Requires Live 12.2+ and an audio track.

        Parameters:
        - track_index: The index of the audio track
        - time: Start time in beats for the new clip
        - length: Length of the clip in beats
        """
        _validate_index(track_index, "track_index")
        if not isinstance(time, (int, float)) or time < 0:
            raise ValueError("time must be a non-negative number")
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")
        ableton = get_ableton_connection()
        result = ableton.send_command("create_arrangement_audio_clip", {
            "track_index": track_index,
            "time": time,
            "length": length,
        })
        return f"Created arrangement audio clip on track {track_index} at beat {time}, length {length}"

    @mcp.tool()
    @_tool_handler("moving arrangement clip")
    def move_arrangement_clip(ctx: Context, track_index: int,
                                clip_index_in_arrangement: int,
                                new_start_time: float) -> str:
        """Move an arrangement clip to a new start position (Live 12.2+).

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        - new_start_time: New start position in beats
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("move_arrangement_clip", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
            "new_start_time": new_start_time,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("deleting arrangement clip")
    def delete_arrangement_clip(ctx: Context, track_index: int,
                                  clip_index_in_arrangement: int) -> str:
        """Delete an arrangement clip by its index.

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("delete_arrangement_clip", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting arrangement clip properties")
    def set_arrangement_clip_properties(ctx: Context, track_index: int,
                                          clip_index_in_arrangement: int,
                                          muted: Optional[bool] = None,
                                          gain: Optional[float] = None,
                                          name: Optional[str] = None,
                                          color_index: Optional[int] = None,
                                          loop_start: Optional[float] = None,
                                          loop_end: Optional[float] = None,
                                          looping: Optional[bool] = None,
                                          start_marker: Optional[float] = None,
                                          end_marker: Optional[float] = None,
                                          pitch_coarse: Optional[int] = None,
                                          pitch_fine: Optional[int] = None) -> str:
        """Set properties on an arrangement clip (mute, gain, name, color, loop, pitch).

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        - muted: Mute/unmute the clip
        - gain: Audio clip gain
        - name: Clip name
        - color_index: Color index
        - loop_start/loop_end: Loop boundaries
        - looping: Enable/disable looping
        - start_marker/end_marker: Clip markers
        - pitch_coarse: Coarse pitch in semitones
        - pitch_fine: Fine pitch in cents
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        params = {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        }
        for key, val in [("muted", muted), ("gain", gain), ("name", name),
                         ("color_index", color_index), ("loop_start", loop_start),
                         ("loop_end", loop_end), ("looping", looping),
                         ("start_marker", start_marker), ("end_marker", end_marker),
                         ("pitch_coarse", pitch_coarse), ("pitch_fine", pitch_fine)]:
            if val is not None:
                params[key] = val
        ableton = get_ableton_connection()
        result = ableton.send_command("set_arrangement_clip_properties", params)
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting arrangement clip info")
    def get_arrangement_clip_info(ctx: Context, track_index: int,
                                    clip_index_in_arrangement: int) -> str:
        """Get detailed info about a specific arrangement clip.

        Parameters:
        - track_index: The track index
        - clip_index_in_arrangement: Index of the clip in track.arrangement_clips
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index_in_arrangement, "clip_index_in_arrangement")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_arrangement_clip_info", {
            "track_index": track_index,
            "clip_index_in_arrangement": clip_index_in_arrangement,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("setting detail clip")
    def set_detail_clip(ctx: Context, track_index: int, clip_index: int) -> str:
        """Show a clip in Live's Detail view (the bottom panel).

        Parameters:
        - track_index: The track containing the clip
        - clip_index: The clip slot index
        """
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("set_detail_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        name = result.get("clip_name", "?")
        return f"Detail view showing clip '{name}' (track {track_index}, slot {clip_index})"

    @mcp.tool()
    @_tool_handler("selecting scene")
    def select_scene(ctx: Context, scene_index: int) -> str:
        """Select a scene by index in Live's Session view.

        Parameters:
        - scene_index: The index of the scene to select (0-based)
        """
        _validate_index(scene_index, "scene_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("select_scene", {"scene_index": scene_index})
        name = result.get("scene_name", "?")
        return f"Selected scene {scene_index}: '{name}'"

    # ==================================================================
    # Arrangement Composition Analysis Tools
    # ==================================================================

    def _get_all_arrangement_clips(ableton, track_count):
        """Helper: fetch arrangement clips for all tracks, skipping failures."""
        all_clips = []
        for i in range(track_count):
            try:
                data = ableton.send_command("get_arrangement_clips", {"track_index": i})
                if data.get("clips"):
                    all_clips.append(data)
            except Exception:
                continue
        return all_clips

    def _try_get_cue_points():
        """Try to get cue points via M4L. Returns list or empty if unavailable."""
        try:
            from MCP_Server.connections.m4l import get_m4l_connection
            from MCP_Server.tools._base import _m4l_result
            m4l = get_m4l_connection()
            result = m4l.send_command("get_cue_points")
            data = _m4l_result(result)
            return data.get("cue_points", [])
        except Exception:
            return []

    @mcp.tool()
    @_tool_handler("getting arrangement overview")
    def get_arrangement_overview(ctx: Context, include_clip_details: bool = True) -> str:
        """Get a high-level overview of the entire arrangement for composition analysis.

        Returns tempo, time signature, song length, per-track clip summaries,
        cue points (if M4L available), and section information.

        Parameters:
        - include_clip_details: Include individual clip start/end/name data (default True)
        """
        ableton = get_ableton_connection()

        # 1. Session info
        session = ableton.send_command("get_session_info")
        tempo = session.get("tempo", 120.0)
        sig_num = session.get("signature_numerator", 4)
        sig_den = session.get("signature_denominator", 4)

        # 2. Song length
        try:
            length_data = ableton.send_command("get_song_length")
            song_length = length_data.get("song_length", 0)
        except Exception:
            song_length = 0

        # 3. All tracks info
        tracks_data = ableton.send_command("get_all_tracks_info")
        tracks_list = tracks_data if isinstance(tracks_data, list) else tracks_data.get("tracks", [])
        track_count = len(tracks_list)

        # 4. Arrangement clips per track
        _report_progress(ctx, 1, 4, "Fetching arrangement clips")
        track_summaries = []
        for i, track in enumerate(tracks_list):
            try:
                clip_data = ableton.send_command("get_arrangement_clips", {"track_index": i})
                clips = clip_data.get("clips", [])
                coverage = 0.0
                if clips and song_length > 0:
                    covered_beats = sum(c.get("length", 0) for c in clips)
                    coverage = min(100.0, (covered_beats / song_length) * 100)

                summary = {
                    "index": i,
                    "name": track.get("name", f"Track {i}"),
                    "type": "audio" if track.get("has_audio_input") else "midi",
                    "clip_count": len(clips),
                    "coverage_percent": round(coverage, 1),
                }
                if include_clip_details and clips:
                    summary["clips"] = [
                        {"name": c.get("name", ""), "start": c.get("start_time", 0),
                         "end": c.get("end_time", 0), "muted": c.get("muted", False)}
                        for c in clips
                    ]
                track_summaries.append(summary)
            except Exception:
                continue

        # 5. Cue points (M4L, graceful fallback)
        _report_progress(ctx, 3, 4, "Fetching cue points")
        cue_points = _try_get_cue_points()

        # 6. Build sections from cue points
        sections = []
        if cue_points:
            sorted_cues = sorted(cue_points, key=lambda c: c.get("time", 0))
            for idx, cue in enumerate(sorted_cues):
                start = cue.get("time", 0)
                end = sorted_cues[idx + 1].get("time", 0) if idx + 1 < len(sorted_cues) else song_length
                sections.append({
                    "name": cue.get("name", f"Section {idx + 1}"),
                    "start_beat": start,
                    "end_beat": end,
                    "bars": round((end - start) / sig_num, 1) if sig_num else 0,
                })

        beats_per_bar = sig_num * (4.0 / sig_den)
        result = {
            "tempo": tempo,
            "time_signature": f"{sig_num}/{sig_den}",
            "song_length_beats": round(song_length, 2),
            "song_length_bars": round(song_length / beats_per_bar, 1) if beats_per_bar else 0,
            "track_count": track_count,
            "tracks": track_summaries,
            "cue_points": [{"name": c.get("name", ""), "time": c.get("time", 0)} for c in cue_points],
            "sections": sections,
        }
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("analyzing arrangement density")
    def analyze_arrangement_density(ctx: Context, region_size_beats: float = 16.0) -> str:
        """Analyze clip density and activity across time regions of the arrangement.

        Divides the song into equal-sized regions and counts active tracks/clips per region.
        Useful for understanding arrangement energy and identifying sparse/dense sections.

        Parameters:
        - region_size_beats: Size of each analysis region in beats (default 16 = 4 bars in 4/4)
        """
        if region_size_beats <= 0:
            raise ValueError("region_size_beats must be positive")

        ableton = get_ableton_connection()

        # Get song length
        try:
            length_data = ableton.send_command("get_song_length")
            song_length = length_data.get("song_length", 0)
        except Exception:
            song_length = 0
        if song_length <= 0:
            return json.dumps({"error": "Song appears empty (length = 0)"})

        # Get all tracks
        tracks_data = ableton.send_command("get_all_tracks_info")
        tracks_list = tracks_data if isinstance(tracks_data, list) else tracks_data.get("tracks", [])
        track_count = len(tracks_list)

        # Fetch clips for all tracks
        _report_progress(ctx, 1, 3, "Fetching clips from all tracks")
        all_track_clips = _get_all_arrangement_clips(ableton, track_count)

        # Divide into regions
        num_regions = math.ceil(song_length / region_size_beats)
        regions = []

        for r in range(num_regions):
            region_start = r * region_size_beats
            region_end = min((r + 1) * region_size_beats, song_length)
            active_tracks = set()
            clip_count = 0

            for track_data in all_track_clips:
                track_idx = track_data.get("track_index")
                for clip in track_data.get("clips", []):
                    cs = clip.get("start_time", 0)
                    ce = clip.get("end_time", 0)
                    # Clip overlaps region?
                    if cs < region_end and ce > region_start and not clip.get("muted", False):
                        active_tracks.add(track_idx)
                        clip_count += 1

            density = len(active_tracks) / track_count if track_count > 0 else 0
            regions.append({
                "start": round(region_start, 2),
                "end": round(region_end, 2),
                "active_tracks": len(active_tracks),
                "clip_count": clip_count,
                "density": round(density, 3),
            })

        # Find peak and quietest
        peak = max(regions, key=lambda r: r["density"]) if regions else None
        quietest = min(regions, key=lambda r: r["density"]) if regions else None

        return json.dumps({
            "region_size_beats": region_size_beats,
            "total_regions": num_regions,
            "track_count": track_count,
            "regions": regions,
            "peak_density_region": peak,
            "quietest_region": quietest,
        })

    @mcp.tool()
    @_tool_handler("analyzing arrangement sections")
    def analyze_arrangement_sections(ctx: Context) -> str:
        """Detect and describe song sections based on cue points and clip patterns.

        Uses cue points as section boundaries (if available via M4L), otherwise
        detects section changes from clip density transitions.
        Returns section characterization (sparse, building, peak, breakdown).
        """
        ableton = get_ableton_connection()

        # Session info
        session = ableton.send_command("get_session_info")
        sig_num = session.get("signature_numerator", 4)
        sig_den = session.get("signature_denominator", 4)
        beats_per_bar = sig_num * (4.0 / sig_den)

        # Song length
        try:
            length_data = ableton.send_command("get_song_length")
            song_length = length_data.get("song_length", 0)
        except Exception:
            song_length = 0
        if song_length <= 0:
            return json.dumps({"error": "Song appears empty"})

        # Get tracks and clips
        tracks_data = ableton.send_command("get_all_tracks_info")
        tracks_list = tracks_data if isinstance(tracks_data, list) else tracks_data.get("tracks", [])
        track_count = len(tracks_list)
        track_names = [t.get("name", f"Track {i}") for i, t in enumerate(tracks_list)]

        _report_progress(ctx, 1, 3, "Analyzing arrangement clips")
        all_track_clips = _get_all_arrangement_clips(ableton, track_count)

        # Get cue points for section boundaries
        cue_points = _try_get_cue_points()

        # Determine section boundaries
        if cue_points:
            sorted_cues = sorted(cue_points, key=lambda c: c.get("time", 0))
            boundaries = [(c.get("name", ""), c.get("time", 0)) for c in sorted_cues]
        else:
            # Auto-detect: analyze in 8-bar chunks, find density transitions
            chunk_size = beats_per_bar * 8
            boundaries = [("Start", 0.0)]
            prev_active = 0
            for r in range(1, math.ceil(song_length / chunk_size)):
                region_start = r * chunk_size
                region_end = min((r + 1) * chunk_size, song_length)
                active = 0
                for td in all_track_clips:
                    for clip in td.get("clips", []):
                        cs = clip.get("start_time", 0)
                        ce = clip.get("end_time", 0)
                        if cs < region_end and ce > region_start and not clip.get("muted", False):
                            active += 1
                            break
                # Detect significant change (>=2 tracks differ)
                if abs(active - prev_active) >= 2:
                    boundaries.append((f"Section at bar {int(region_start / beats_per_bar) + 1}", region_start))
                prev_active = active

        # Analyze each section
        sections = []
        for idx in range(len(boundaries)):
            name, start = boundaries[idx]
            end = boundaries[idx + 1][1] if idx + 1 < len(boundaries) else song_length
            if end <= start:
                continue

            # Count active tracks in this section
            active_track_names = []
            clip_count = 0
            for td in all_track_clips:
                track_idx = td.get("track_index", 0)
                has_content = False
                for clip in td.get("clips", []):
                    cs = clip.get("start_time", 0)
                    ce = clip.get("end_time", 0)
                    if cs < end and ce > start and not clip.get("muted", False):
                        has_content = True
                        clip_count += 1
                if has_content and track_idx < len(track_names):
                    active_track_names.append(track_names[track_idx])

            density = len(active_track_names) / track_count if track_count > 0 else 0

            # Characterize
            if density < 0.2:
                character = "sparse"
            elif density < 0.4:
                character = "light"
            elif density < 0.6:
                character = "moderate"
            elif density < 0.8:
                character = "dense"
            else:
                character = "peak"

            # Detect building/dropping by comparing to neighbors
            if idx > 0 and sections:
                prev_density = sections[-1].get("density", 0)
                if density - prev_density > 0.2:
                    character = "building"
                elif prev_density - density > 0.2:
                    character = "breakdown"

            bars = round((end - start) / beats_per_bar, 1)
            sections.append({
                "name": name,
                "start_beat": round(start, 2),
                "end_beat": round(end, 2),
                "bars": bars,
                "active_tracks": active_track_names,
                "clip_count": clip_count,
                "density": round(density, 3),
                "character": character,
            })

        # Build form summary
        form_parts = [f"{s['name']}({int(s['bars'])})" for s in sections]
        form_summary = " → ".join(form_parts) if form_parts else ""

        return json.dumps({
            "sections": sections,
            "section_count": len(sections),
            "form_summary": form_summary,
            "cue_points_available": bool(cue_points),
        })

    @mcp.tool()
    @_tool_handler("analyzing note content")
    def analyze_note_content(ctx: Context, track_index: int = -1) -> str:
        """Analyze note content across arrangement clips for compositional insights.

        Computes pitch range, note density, velocity stats, and estimated key/scale.
        Can analyze a single track or all MIDI tracks (-1).

        Parameters:
        - track_index: Track to analyze (-1 for all MIDI tracks, default)
        """
        ableton = get_ableton_connection()

        # Determine which tracks to analyze
        if track_index >= 0:
            track_indices = [track_index]
        else:
            tracks_data = ableton.send_command("get_all_tracks_info")
            tracks_list = tracks_data if isinstance(tracks_data, list) else tracks_data.get("tracks", [])
            track_indices = [i for i, t in enumerate(tracks_list)
                           if not t.get("has_audio_input", False)]

        # Collect notes from arrangement clips
        all_notes = []
        tracks_analyzed = []

        _report_progress(ctx, 1, 3, "Reading arrangement clips")
        for idx in track_indices:
            try:
                clip_data = ableton.send_command("get_arrangement_clips", {"track_index": idx})
                clips = clip_data.get("clips", [])
                midi_clips = [c for c in clips if c.get("is_midi_clip", False)]
                if not midi_clips:
                    continue

                # Get notes from each clip via get_clip_notes (arrangement)
                # We need clip_index_in_arrangement — use index in list
                track_notes = []
                for ci, clip in enumerate(midi_clips):
                    try:
                        # For arrangement clips, use the arrangement clip index
                        # Find the index in the full clip list
                        arr_idx = clips.index(clip)
                        notes_result = ableton.send_command("get_clip_notes", {
                            "track_index": idx,
                            "clip_index": arr_idx,
                            "start_time": 0.0,
                            "time_span": 0.0,
                            "start_pitch": 0,
                            "pitch_span": 128,
                        })
                        notes = notes_result.get("notes", [])
                        track_notes.extend(notes)
                    except Exception:
                        continue

                if track_notes:
                    all_notes.extend(track_notes)
                    tracks_analyzed.append({
                        "index": idx,
                        "name": clip_data.get("track_name", f"Track {idx}"),
                        "note_count": len(track_notes),
                    })
            except Exception:
                continue

        if not all_notes:
            return json.dumps({"error": "No MIDI notes found in arrangement clips",
                             "tracks_checked": len(track_indices)})

        # Compute statistics
        pitches = [n.get("pitch", 60) for n in all_notes]
        velocities = [n.get("velocity", 100) for n in all_notes]
        durations = [n.get("duration", 0.5) for n in all_notes]

        # Pitch class distribution (for key detection)
        pitch_classes = [0] * 12
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        for p in pitches:
            pitch_classes[p % 12] += 1

        # Key detection using Krumhansl-Schmuckler profiles
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

        best_key = "C major"
        best_score = -999
        total_notes_count = sum(pitch_classes)

        if total_notes_count > 0:
            # Normalize pitch class distribution
            pc_norm = [c / total_notes_count for c in pitch_classes]
            for root in range(12):
                # Rotate distribution to test this root
                rotated = pc_norm[root:] + pc_norm[:root]
                # Correlate with major
                major_score = sum(a * b for a, b in zip(rotated, major_profile))
                if major_score > best_score:
                    best_score = major_score
                    best_key = f"{note_names[root]} major"
                # Correlate with minor
                minor_score = sum(a * b for a, b in zip(rotated, minor_profile))
                if minor_score > best_score:
                    best_score = minor_score
                    best_key = f"{note_names[root]} minor"

        # Pitch class distribution as dict
        pc_dict = {note_names[i]: pitch_classes[i] for i in range(12) if pitch_classes[i] > 0}

        result = {
            "tracks_analyzed": tracks_analyzed,
            "total_notes": len(all_notes),
            "pitch_range": {
                "lowest": min(pitches),
                "highest": max(pitches),
                "span": max(pitches) - min(pitches),
                "lowest_name": note_names[min(pitches) % 12] + str(min(pitches) // 12 - 1),
                "highest_name": note_names[max(pitches) % 12] + str(max(pitches) // 12 - 1),
            },
            "velocity": {
                "min": min(velocities),
                "max": max(velocities),
                "avg": round(sum(velocities) / len(velocities), 1),
            },
            "note_duration_avg": round(sum(durations) / len(durations), 3),
            "pitch_class_distribution": pc_dict,
            "estimated_key": best_key,
        }
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("comparing arrangement sections")
    def compare_arrangement_sections(
        ctx: Context,
        section_a_start: float, section_a_end: float,
        section_b_start: float, section_b_end: float,
    ) -> str:
        """Compare two time regions of the arrangement for structural similarity.

        Analyzes which tracks are active, clip density, and content overlap.
        Useful for checking if two choruses/verses are identical or how they differ.

        Parameters:
        - section_a_start: Start beat of first section
        - section_a_end: End beat of first section
        - section_b_start: Start beat of second section
        - section_b_end: End beat of second section
        """
        if section_a_end <= section_a_start:
            raise ValueError("section_a_end must be greater than section_a_start")
        if section_b_end <= section_b_start:
            raise ValueError("section_b_end must be greater than section_b_start")

        ableton = get_ableton_connection()
        tracks_data = ableton.send_command("get_all_tracks_info")
        tracks_list = tracks_data if isinstance(tracks_data, list) else tracks_data.get("tracks", [])
        track_count = len(tracks_list)
        track_names = [t.get("name", f"Track {i}") for i, t in enumerate(tracks_list)]

        all_track_clips = _get_all_arrangement_clips(ableton, track_count)

        def get_section_info(start, end):
            """Analyze a section's content."""
            active_tracks = set()
            clip_names = []
            for td in all_track_clips:
                track_idx = td.get("track_index", 0)
                for clip in td.get("clips", []):
                    cs = clip.get("start_time", 0)
                    ce = clip.get("end_time", 0)
                    if cs < end and ce > start and not clip.get("muted", False):
                        active_tracks.add(track_idx)
                        clip_names.append(clip.get("name", ""))
            return active_tracks, clip_names

        tracks_a, clips_a = get_section_info(section_a_start, section_a_end)
        tracks_b, clips_b = get_section_info(section_b_start, section_b_end)

        # Jaccard similarity on active tracks
        if tracks_a or tracks_b:
            track_similarity = len(tracks_a & tracks_b) / len(tracks_a | tracks_b)
        else:
            track_similarity = 1.0

        # Clip name overlap (how many clips share names)
        names_a = set(n for n in clips_a if n)
        names_b = set(n for n in clips_b if n)
        if names_a or names_b:
            name_similarity = len(names_a & names_b) / len(names_a | names_b)
        else:
            name_similarity = 0.0

        # Density similarity
        density_a = len(tracks_a) / track_count if track_count > 0 else 0
        density_b = len(tracks_b) / track_count if track_count > 0 else 0
        density_diff = abs(density_a - density_b)

        # Overall similarity (weighted average)
        overall = 0.5 * track_similarity + 0.3 * name_similarity + 0.2 * (1.0 - density_diff)

        # Differences
        only_in_a = [track_names[t] for t in tracks_a - tracks_b if t < len(track_names)]
        only_in_b = [track_names[t] for t in tracks_b - tracks_a if t < len(track_names)]

        return json.dumps({
            "section_a": {"start": section_a_start, "end": section_a_end,
                         "active_tracks": len(tracks_a), "density": round(density_a, 3)},
            "section_b": {"start": section_b_start, "end": section_b_end,
                         "active_tracks": len(tracks_b), "density": round(density_b, 3)},
            "similarity": {
                "overall": round(overall, 3),
                "track_similarity": round(track_similarity, 3),
                "clip_name_similarity": round(name_similarity, 3),
                "density_difference": round(density_diff, 3),
            },
            "differences": {
                "tracks_only_in_a": only_in_a,
                "tracks_only_in_b": only_in_b,
            },
            "verdict": "identical" if overall > 0.95 else
                      "very similar" if overall > 0.8 else
                      "similar" if overall > 0.6 else
                      "somewhat different" if overall > 0.4 else
                      "very different",
        })
