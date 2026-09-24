"""V2 bounded workflow: exactly two model calls in every condition, at most one tool execution.

V1's loop (src/agent.py) is frozen and unchanged; this module reuses V1's
parser (evaluate.parse_response) and tool allowlist/validator
(tools.validate_request, tools.TOOLS).

Turn 1: the model returns an intermediate final answer or a tool request.
Turn 2: a fresh model call whose prompt contains the original task, the model's
previous public reply and a "tool section" that says exactly what happened to
any tool request. The final answer is always turn 2's reply.

Conditions:
  no_tool        no tool is offered; a tool request is recorded and not executed.
  optional_tool  the model may request fit_line (V1 wording).
  required_tool  the model must request fit_line first; a final answer at turn 1
                 is recorded as noncompliance, and the episode still gets turn 2.
A transport failure at turn 1 (no reply at all) ends the episode: missing_output,
no retry. Model text that fails to parse still gets the fixed second turn.

The loop mutates a caller-supplied state dict in place (new_state), so that a
control violation raised by call_model at turn 2 leaves the turn-1 and tool
evidence intact in the saved record.
"""
import json
from string import Template

import evaluate
import tools

MAX_MODEL_CALLS = 2
MAX_TOOL_EXECUTIONS = 1
CONDITIONS = ("no_tool", "optional_tool", "required_tool")
TOOL_CONDITIONS = ("optional_tool", "required_tool")

NO_FURTHER = " No further tool use is available."
SECTIONS = {
    ("no_tool", "final"): "You may check your calculation and revise your answer.",
    ("no_tool", "tool"): "No tool is available in this task, so there is no tool result.",
    ("no_tool", "unparsed"): "Your previous reply was not a valid JSON object of the required form.",
    ("optional_tool", "final"): "No tool was requested, so there is no tool result. You may check your calculation "
                                "and revise your answer." + NO_FURTHER,
    ("optional_tool", "unparsed"): "Your previous reply was not a valid JSON object of the required form, so there "
                                   "is no tool result." + NO_FURTHER,
    ("required_tool", "final"): "A tool request was required, but your reply was a final answer instead, so there "
                                "is no tool result." + NO_FURTHER,
    ("required_tool", "unparsed"): "A tool request was required, but your previous reply was not a valid JSON "
                                   "object of the required form, so there is no tool result." + NO_FURTHER,
}


def parse(text):
    """V1's parser, with parser exceptions recorded as outcomes instead of crashes: a huge JSON integer
    (e.g. 10**400) raises OverflowError in the finite-number check; deeply nested JSON raises
    RecursionError; an integer literal over 4,300 digits raises a plain ValueError from json.loads."""
    try:
        return evaluate.parse_response(text)
    except OverflowError:
        return None, None, "bad_acceleration"
    except (RecursionError, ValueError):
        return None, None, "malformed_json"


def echo_safe(text):
    """The previous reply is echoed verbatim into the next prompt; a lone surrogate would make the
    CLI subprocess's UTF-8 encoding fail, so such code points are replaced (the saved record keeps
    the original text)."""
    return text.encode("utf-8", "replace").decode("utf-8")


def empty_tool_record():
    return {"requested": False, "request": None, "valid": None, "validation_error": None,
            "executed": False, "result": None, "execution_error": None}


def new_state(condition):
    """The episode state the loop fills in. required_compliant stays None until turn 1 has replied."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition}")
    return {"answer": None, "error": None, "model_calls": 0, "tool_executions": 0, "turn_kinds": [],
            "turn1": {"kind": None, "answer": None, "error": None}, "tool": empty_tool_record(),
            "required_compliant": None, "tool_section": None, "turn2_prompt": None}


def run_episode_v2(case, condition, turn1_prompt, turn2_template, call_model, state=None):
    """Run one episode. call_model(prompt, turn) returns the response text, or None for no reply.

    Returns the state: the final answer (or None), an outcome error code (or None), the turn-1
    record, the tool record, compliance, and the counts needed for the trace.
    """
    out = new_state(condition) if state is None else state
    text = call_model(turn1_prompt, 1)
    out["model_calls"] = 1
    kind, obj, error = parse(text)
    out["turn_kinds"].append(kind or error)
    out["turn1"] = {"kind": kind, "answer": obj if kind == "final" else None, "error": error}
    if error == "missing_output":
        out["error"] = "missing_output"  # no reply at all: the episode ends, no retry (V1 rule D5)
        return out
    if condition == "required_tool":
        out["required_compliant"] = False  # turn 1 replied; only a valid request below makes this True

    if kind == "tool":
        tool = out["tool"]
        tool["requested"], tool["request"] = True, obj
        if condition == "no_tool":
            tool["valid"], tool["validation_error"] = False, "no_tool_condition"
            section = SECTIONS[("no_tool", "tool")]
        else:
            problem = tools.validate_request(obj, case["id"])
            if problem:
                tool["valid"], tool["validation_error"] = False, problem
                section = f"The tool request was not valid ({problem}), so there is no tool result." + NO_FURTHER
            else:
                tool["valid"] = True
                if condition == "required_tool":
                    out["required_compliant"] = True  # compliance = a valid request; execution is the harness's job
                out["tool_executions"] = 1
                try:
                    result = tools.TOOLS[obj["name"]](case)  # the tool sees the displayed case only, never the key
                except Exception as exc:  # recorded as an outcome, never retried
                    tool["execution_error"] = f"tool_error:{type(exc).__name__}"
                    section = ("The tool request was valid, but the tool failed to run, so there is no tool "
                               "result." + NO_FURTHER)
                else:
                    tool["executed"], tool["result"] = True, result
                    section = "Tool result (fit_line):\n" + json.dumps(result) + NO_FURTHER
    elif kind == "final":
        section = SECTIONS[(condition, "final")]
    else:
        section = SECTIONS[(condition, "unparsed")]
    out["tool_section"] = section

    turn2_prompt = Template(turn2_template).substitute(
        original_task=turn1_prompt.rstrip("\n"), previous_response=echo_safe(text.strip()), tool_section=section)
    out["turn2_prompt"] = turn2_prompt
    text2 = call_model(turn2_prompt, 2)
    out["model_calls"] = 2
    kind2, obj2, error2 = parse(text2)
    out["turn_kinds"].append(kind2 or error2)
    if error2:
        out["error"] = error2
    elif kind2 == "tool":
        out["error"] = "tool_request_at_final_turn"  # a second request; nothing is executed
    else:
        out["answer"] = obj2
    return out
