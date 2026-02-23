"""Input validation helpers for AbletonBridge MCP tools."""
import math
import logging

logger = logging.getLogger("AbletonBridge")

# Phase 4.4: Input size limits
MAX_NOTES_PER_CALL = 10_000
MAX_AUTOMATION_POINTS = 500
MAX_BATCH_PARAMS = 200
MAX_TRACKS_PER_BATCH = 50
MAX_SEARCH_QUERY_LENGTH = 500


def _validate_index(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value}.")


def _validate_index_allow_negative(value: int, name: str, min_value: int = -1) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}.")


def _validate_range(value: float, name: str, min_val: float, max_val: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    if value < min_val or value > max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}.")


def _validate_notes(notes: list) -> None:
    if not isinstance(notes, list):
        raise ValueError("notes must be a list.")
    if len(notes) == 0:
        raise ValueError("notes list must not be empty.")
    if len(notes) > MAX_NOTES_PER_CALL:
        raise ValueError(f"Too many notes ({len(notes)}). Maximum is {MAX_NOTES_PER_CALL} per call.")
    required_keys = {"pitch", "start_time", "duration", "velocity"}
    for i, note in enumerate(notes):
        if not isinstance(note, dict):
            raise ValueError(f"Each note must be a dictionary (note at index {i} is not).")
        missing = required_keys - note.keys()
        if missing:
            raise ValueError(f"Note at index {i} is missing required keys: {', '.join(sorted(missing))}.")
        pitch = note["pitch"]
        if not isinstance(pitch, int) or isinstance(pitch, bool) or pitch < 0 or pitch > 127:
            raise ValueError(f"Note at index {i}: pitch must be an integer between 0 and 127, got {pitch}.")
        velocity = note["velocity"]
        if not isinstance(velocity, (int, float)) or isinstance(velocity, bool) or velocity < 0 or velocity > 127:
            raise ValueError(f"Note at index {i}: velocity must be a number between 0 and 127, got {velocity}.")
        duration = note["duration"]
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            raise ValueError(f"Note at index {i}: duration must be a positive number, got {duration}.")
        start_time = note["start_time"]
        if not isinstance(start_time, (int, float)) or isinstance(start_time, bool) or start_time < 0:
            raise ValueError(f"Note at index {i}: start_time must be a non-negative number, got {start_time}.")


def _validate_automation_points(points: list) -> None:
    if not isinstance(points, list):
        raise ValueError("automation_points must be a list.")
    if len(points) == 0:
        raise ValueError("automation_points list must not be empty.")
    if len(points) > MAX_AUTOMATION_POINTS:
        raise ValueError(f"Too many automation points ({len(points)}). Maximum is {MAX_AUTOMATION_POINTS}.")
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            raise ValueError(f"Each automation point must be a dictionary (point at index {i} is not).")
        if "time" not in point or "value" not in point:
            raise ValueError(f"Automation point at index {i} must have 'time' and 'value' keys.")
        time_val = point["time"]
        if not isinstance(time_val, (int, float)) or isinstance(time_val, bool) or time_val < 0:
            raise ValueError(f"Automation point at index {i}: time must be a non-negative number, got {time_val}.")
        val = point["value"]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ValueError(f"Automation point at index {i}: value must be a number, got {val}.")


def _perpendicular_distance(at, av, bt, bv, ct, cv):
    """Perpendicular distance of point B from line A->C (pre-normalized coords)."""
    dt = ct - at
    dv = cv - av
    length_sq = dt * dt + dv * dv
    if length_sq == 0.0:
        return math.sqrt((bt - at) ** 2 + (bv - av) ** 2)
    return abs(dv * (bt - at) - dt * (bv - av)) / math.sqrt(length_sq)


def _rdp_recursive(norm_points, epsilon):
    """Ramer-Douglas-Peucker on list of (norm_t, norm_v, original_dict)."""
    if len(norm_points) <= 2:
        return [p[2] for p in norm_points]
    first = norm_points[0]
    last = norm_points[-1]
    max_dist = 0.0
    max_idx = 1
    for i in range(1, len(norm_points) - 1):
        p = norm_points[i]
        d = _perpendicular_distance(first[0], first[1], p[0], p[1], last[0], last[1])
        if d > max_dist:
            max_dist = d
            max_idx = i
    if max_dist > epsilon:
        left = _rdp_recursive(norm_points[:max_idx + 1], epsilon)
        right = _rdp_recursive(norm_points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [first[2], last[2]]


def _reduce_automation_points(points, max_points=20, time_epsilon=0.001,
                               collinear_epsilon=0.005):
    """Reduce automation point density while preserving shape.

    Three-stage pipeline:
    1. Sort by time, deduplicate points at same/close times (keep last)
    2. Remove collinear points (redundant under linear interpolation)
    3. If still over max_points, apply RDP simplification
    """
    if len(points) <= 2:
        return points

    original_count = len(points)

    # Stage 1: sort by time, deduplicate clustered times
    sorted_pts = sorted(points, key=lambda p: (p["time"], p.get("value", 0)))
    deduped = [sorted_pts[0]]
    for pt in sorted_pts[1:]:
        if pt["time"] - deduped[-1]["time"] < time_epsilon:
            deduped[-1] = pt  # last value at this time wins
        else:
            deduped.append(pt)

    if len(deduped) <= 2:
        if len(deduped) != original_count:
            logger.info("Automation point reduction: %d -> %d points", original_count, len(deduped))
        return deduped

    # Normalization spans for stages 2 and 3
    times = [p["time"] for p in deduped]
    values = [p["value"] for p in deduped]
    t_min, t_max = min(times), max(times)
    v_min, v_max = min(values), max(values)
    t_span = (t_max - t_min) or 1.0
    v_span = (v_max - v_min) or 1.0

    def nt(t):
        return (t - t_min) / t_span

    def nv(v):
        return (v - v_min) / v_span

    # Stage 2: remove collinear points
    result = [deduped[0]]
    for i in range(1, len(deduped) - 1):
        A = result[-1]
        B = deduped[i]
        C = deduped[i + 1]
        dist = _perpendicular_distance(
            nt(A["time"]), nv(A["value"]),
            nt(B["time"]), nv(B["value"]),
            nt(C["time"]), nv(C["value"]),
        )
        if dist > collinear_epsilon:
            result.append(B)
    result.append(deduped[-1])

    # Stage 3: RDP cap if still over max_points
    if len(result) > max_points:
        norm_pts = [(nt(p["time"]), nv(p["value"]), p) for p in result]
        eps = 0.005
        for _ in range(20):
            reduced = _rdp_recursive(norm_pts, eps)
            if len(reduced) <= max_points:
                result = reduced
                break
            eps *= 2.0
        else:
            # Fallback: uniform sampling
            indices = [0, len(result) - 1]
            for j in range(1, max_points - 1):
                idx = round(j * (len(result) - 1) / (max_points - 1))
                if idx not in indices:
                    indices.append(idx)
            indices.sort()
            result = [result[i] for i in indices[:max_points]]

    if len(result) != original_count:
        logger.info("Automation point reduction: %d -> %d points", original_count, len(result))

    return result
