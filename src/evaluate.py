"""Parse and grade final answers.

Written by Claude at Leo's direction (2026-09-21). Rules follow EXPERIMENT.md
sections 5 and 7: exactly one JSON object, no repair, no retry.
"""
import json
import math

ACCEPTED_UNITS = ("m/s^2", "m/s²", "m s^-2")
DEV_TOLERANCE = 0.01  # m/s^2, absolute, PROVISIONAL (development only)


def parse_final(text):
    """Return (answer, error_code). Surrounding whitespace is allowed; nothing else."""
    if text is None or not text.strip():
        return None, "missing_output"
    try:
        obj = json.loads(text.strip())
    except json.JSONDecodeError:
        return None, "malformed_json"
    if not isinstance(obj, dict):
        return None, "not_an_object"
    if obj.get("type") != "final":
        return None, "wrong_type"
    a = obj.get("acceleration")
    if isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a):
        return None, "bad_acceleration"
    return {"acceleration": float(a), "units": obj.get("units")}, None


def grade(answer, error, a_ref, tol=DEV_TOLERANCE):
    """Outcome is one of: correct, wrong_value, wrong_units, or the parse error code."""
    if error:
        return {"correct": False, "outcome": error, "abs_error": None}
    abs_error = abs(answer["acceleration"] - a_ref)
    if answer["units"] not in ACCEPTED_UNITS:
        return {"correct": False, "outcome": "wrong_units", "abs_error": abs_error}
    ok = abs_error <= tol
    return {"correct": ok, "outcome": "correct" if ok else "wrong_value", "abs_error": abs_error}


def parse_response(text):
    """Workflow turn. Return ("final", answer, None), ("tool", request, None) or (None, None, error)."""
    if text is None or not text.strip():
        return None, None, "missing_output"
    try:
        obj = json.loads(text.strip())
    except json.JSONDecodeError:
        return None, None, "malformed_json"
    if isinstance(obj, dict) and obj.get("type") == "tool":
        return "tool", obj, None
    answer, error = parse_final(text)
    return ("final", answer, None) if error is None else (None, None, error)
