"""Bounded tool workflow: at most two model calls and one tool execution.

Written by Claude at Leo's direction (2026-09-21). The model only proposes an
action as JSON text; this loop validates it and executes allowlisted tools.
No retries. Turn 2 is a fresh model call whose prompt contains the original
task, the model's previous public reply and the tool result.
"""
import json
from string import Template

import evaluate
import tools

MAX_MODEL_CALLS = 2
MAX_TOOL_EXECUTIONS = 1


def run_workflow(case, turn1_prompt, turn2_template, call_model):
    """Run one episode. call_model(prompt, turn) returns the response text or None.

    Returns the final answer (or None), an outcome error code (or None), and the
    counts and tool record needed for the trace.
    """
    out = {"answer": None, "error": None, "model_calls": 0, "tool_executions": 0,
           "tool": None, "turn_kinds": [], "turn2_prompt": None}

    text = call_model(turn1_prompt, 1)
    out["model_calls"] = 1
    kind, obj, error = evaluate.parse_response(text)
    out["turn_kinds"].append(kind or error)
    if error:
        out["error"] = error
        return out
    if kind == "final":
        out["answer"] = obj
        return out

    problem = tools.validate_request(obj, case["id"])
    if problem:
        out["tool"] = {"request": obj, "executed": False, "error": problem}
        out["error"] = "invalid_tool_request"
        return out
    out["tool_executions"] = 1
    try:
        result = tools.TOOLS[obj["name"]](case)
    except Exception as exc:  # recorded as an outcome, never retried
        out["tool"] = {"request": obj, "executed": False, "error": f"tool_error:{type(exc).__name__}"}
        out["error"] = "tool_error"
        return out
    out["tool"] = {"request": obj, "executed": True, "error": None, "result": result}

    turn2_prompt = Template(turn2_template).substitute(
        original_task=turn1_prompt.rstrip("\n"),
        previous_response=text.strip(),
        tool_result=json.dumps(result),
    )
    out["turn2_prompt"] = turn2_prompt
    text2 = call_model(turn2_prompt, 2)
    out["model_calls"] = 2
    kind2, obj2, error2 = evaluate.parse_response(text2)
    out["turn_kinds"].append(kind2 or error2)
    if error2:
        out["error"] = error2
    elif kind2 == "tool":
        out["error"] = "tool_limit_exceeded"
    else:
        out["answer"] = obj2
    return out
