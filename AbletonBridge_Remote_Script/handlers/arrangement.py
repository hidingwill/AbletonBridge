"""Arrangement: copy clip to arrangement, get arrangement clips, manipulate arrangement clips."""

from __future__ import absolute_import, print_function, unicode_literals

import traceback

from ._helpers import get_track, get_clip


def _get_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl=None):
    """Get an arrangement clip by its index in the arrangement_clips list."""
    track = get_track(song, track_index)
    if not hasattr(track, "arrangement_clips"):
        raise Exception("Track does not have arrangement clips")
    arr_clips = list(track.arrangement_clips)
    if clip_index_in_arrangement < 0 or clip_index_in_arrangement >= len(arr_clips):
        raise IndexError("Arrangement clip index {0} out of range (track has {1} arrangement clips)".format(
            clip_index_in_arrangement, len(arr_clips)))
    return track, arr_clips[clip_index_in_arrangement]


def duplicate_clip_to_arrangement(song, track_index, clip_index, time, ctrl=None):
    """Copy a session clip to the arrangement timeline."""
    try:
        track, clip = get_clip(song, track_index, clip_index)

        if not hasattr(track, 'duplicate_clip_to_arrangement'):
            raise Exception("duplicate_clip_to_arrangement requires Live 11 or later")

        time = max(0.0, float(time))
        track.duplicate_clip_to_arrangement(clip, time)

        return {
            "placed_at": time,
            "clip_name": clip.name,
            "clip_length": clip.length,
            "track_index": track_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating clip to arrangement: " + str(e))
        raise


def get_arrangement_clips(song, track_index, ctrl=None):
    """Get all clips in arrangement view for a track."""
    try:
        track = get_track(song, track_index)

        if not hasattr(track, "arrangement_clips"):
            raise Exception(
                "Track does not have arrangement clips "
                "(may be a group track or return track)"
            )

        clips = []
        for clip in track.arrangement_clips:
            clip_info = {
                "name": clip.name,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "length": clip.length,
                "loop_start": getattr(clip, "loop_start", None),
                "loop_end": getattr(clip, "loop_end", None),
                "is_audio_clip": clip.is_audio_clip if hasattr(clip, 'is_audio_clip') else False,
                "is_midi_clip": clip.is_midi_clip if hasattr(clip, 'is_midi_clip') else False,
                "muted": getattr(clip, "muted", False),
                "color_index": getattr(clip, "color_index", None),
            }
            clips.append(clip_info)

        return {
            "track_index": track_index,
            "track_name": track.name,
            "clip_count": len(clips),
            "clips": clips,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting arrangement clips: " + str(e))
        raise


# --- v4.0: Arrangement clip manipulation ---


def move_arrangement_clip(song, track_index, clip_index_in_arrangement, new_start_time, ctrl=None):
    """Move an arrangement clip to a new start position (Live 12.2+)."""
    try:
        track, clip = _get_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl)
        old_start = clip.start_time
        new_start_time = float(new_start_time)
        if new_start_time < 0:
            raise ValueError("new_start_time must be >= 0")
        clip.start_time = new_start_time
        return {
            "track_index": track_index,
            "clip_name": clip.name,
            "old_start_time": old_start,
            "new_start_time": new_start_time,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error moving arrangement clip: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def delete_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl=None):
    """Delete an arrangement clip by its index in the arrangement."""
    try:
        track, clip = _get_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl)
        clip_name = clip.name
        clip_start = clip.start_time
        track.delete_clip(clip)
        return {
            "deleted": True,
            "track_index": track_index,
            "clip_name": clip_name,
            "was_at_time": clip_start,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error deleting arrangement clip: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def set_arrangement_clip_properties(song, track_index, clip_index_in_arrangement,
                                     muted=None, gain=None, name=None, color_index=None,
                                     loop_start=None, loop_end=None, looping=None,
                                     start_marker=None, end_marker=None,
                                     pitch_coarse=None, pitch_fine=None, ctrl=None):
    """Set properties on an arrangement clip (mute, gain, name, color, loop, pitch)."""
    try:
        track, clip = _get_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl)
        changes = {}
        if muted is not None:
            clip.muted = bool(muted)
            changes["muted"] = clip.muted
        if gain is not None:
            clip.gain = float(gain)
            changes["gain"] = clip.gain
        if name is not None:
            clip.name = str(name)
            changes["name"] = clip.name
        if color_index is not None:
            clip.color_index = int(color_index)
            changes["color_index"] = clip.color_index
        if loop_start is not None:
            clip.loop_start = float(loop_start)
            changes["loop_start"] = clip.loop_start
        if loop_end is not None:
            clip.loop_end = float(loop_end)
            changes["loop_end"] = clip.loop_end
        if looping is not None:
            clip.looping = bool(looping)
            changes["looping"] = clip.looping
        if start_marker is not None:
            clip.start_marker = float(start_marker)
            changes["start_marker"] = clip.start_marker
        if end_marker is not None:
            clip.end_marker = float(end_marker)
            changes["end_marker"] = clip.end_marker
        if pitch_coarse is not None:
            clip.pitch_coarse = int(pitch_coarse)
            changes["pitch_coarse"] = clip.pitch_coarse
        if pitch_fine is not None:
            clip.pitch_fine = int(pitch_fine)
            changes["pitch_fine"] = clip.pitch_fine
        if not changes:
            raise ValueError("No properties specified")
        changes["track_index"] = track_index
        changes["arrangement_clip_index"] = clip_index_in_arrangement
        changes["clip_name"] = clip.name
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting arrangement clip properties: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def get_arrangement_clip_info(song, track_index, clip_index_in_arrangement, ctrl=None):
    """Get detailed info about a specific arrangement clip."""
    try:
        track, clip = _get_arrangement_clip(song, track_index, clip_index_in_arrangement, ctrl)
        result = {
            "track_index": track_index,
            "arrangement_clip_index": clip_index_in_arrangement,
            "name": clip.name,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "length": clip.length,
            "is_audio_clip": getattr(clip, "is_audio_clip", False),
            "is_midi_clip": getattr(clip, "is_midi_clip", False),
            "muted": getattr(clip, "muted", False),
            "color_index": getattr(clip, "color_index", None),
        }
        for prop in ("looping", "loop_start", "loop_end", "start_marker", "end_marker",
                      "warping", "warp_mode", "gain", "pitch_coarse", "pitch_fine",
                      "signature_numerator", "signature_denominator", "velocity_amount",
                      "has_envelopes", "ram_mode", "legato"):
            try:
                result[prop] = getattr(clip, prop)
            except Exception:
                pass
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting arrangement clip info: " + str(e))
        raise
