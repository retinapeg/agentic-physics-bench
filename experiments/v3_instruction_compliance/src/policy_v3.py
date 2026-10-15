"""V3 policy cells, prompt rendering and tool-section strings.

Every cell shows the same task, the same tool description and the same reply format; only one slot
differs (PROTOCOL.md section 3). The policy strings live in prompts/policy_*.txt, the single source.
"""
import json
from string import Template

import common_v3 as C
import agent_v2                   # frozen V2 module: SECTIONS, NO_FURTHER

CELLS = ("A", "B", "C_YES", "C_NO", "D")
PERMISSION = {"A": "permitted", "B": "permitted", "C_YES": "permitted", "C_NO": "prohibited", "D": "prohibited"}
POLICY_FILE = {"A": "policy_A.txt", "B": "policy_B.txt", "C_YES": "policy_C.txt", "C_NO": "policy_C.txt",
               "D": "policy_D.txt"}
POLICY_VARS = {"A": {}, "B": {}, "C_YES": {"permission": "YES"}, "C_NO": {"permission": "NO"}, "D": {}}


def _read(name):
    return (C.PROMPTS / name).read_text().rstrip("\n")


def policy_text(cell):
    """The exact policy sentence(s) for a cell ('' for A). Identifier sets are checked both ways."""
    template = Template(_read(POLICY_FILE[cell]))
    wanted, given = set(template.get_identifiers()), set(POLICY_VARS[cell])
    if wanted != given:
        raise ValueError(f"cell {cell}: policy template wants {sorted(wanted)}, cell supplies {sorted(given)}")
    return template.substitute(POLICY_VARS[cell])


POLICY = {cell: policy_text(cell) for cell in CELLS}

# Tool-section strings shown at turn 2. Two are V2's own (imported); three are V2's text, copied; one is new.
SECTION_FINAL = agent_v2.SECTIONS[("optional_tool", "final")]
SECTION_UNPARSED = agent_v2.SECTIONS[("optional_tool", "unparsed")]
SECTION_DENIED = "The tool request was not executed, so there is no tool result." + agent_v2.NO_FURTHER


def section_invalid(code):
    return f"The tool request was not valid ({code}), so there is no tool result." + agent_v2.NO_FURTHER


def section_failed():
    return "The tool request was valid, but the tool failed to run, so there is no tool result." + agent_v2.NO_FURTHER


def section_result(result):
    return "Tool result (fit_line):\n" + json.dumps(result) + agent_v2.NO_FURTHER


def render_task(case):
    """V2's task block, rendered exactly as V2 renders it."""
    template = (C.V2_PROMPTS / "task.txt").read_text()
    return Template(template).substitute(case_id=case["id"], t=", ".join(case["t_s"]), v=", ".join(case["v_m_per_s"]))


def render_turn1(case, cell):
    """The turn-1 prompt for one case and cell. Two-stage rendering with identifier checks at each stage."""
    if cell not in CELLS:
        raise ValueError(f"unknown cell {cell}")
    base = Template((C.PROMPTS / "turn1_base.txt").read_text())
    if set(base.get_identifiers()) != {"task", "case_id", "policy"}:
        raise ValueError("turn1_base.txt must use exactly $task, $case_id and $policy")
    policy = "" if cell == "A" else "\n" + POLICY[cell] + "\n"
    prompt = base.substitute(task=render_task(case).rstrip("\n"), case_id=case["id"], policy=policy)
    assert "$" not in prompt and POLICY[cell] in prompt
    return prompt


def turn2_template():
    return (C.V2_PROMPTS / "turn2.txt").read_text()


def template_hashes(cell):
    return {"v2_task": C.sha256_file(C.V2_PROMPTS / "task.txt"), "turn1_base": C.sha256_file(C.PROMPTS / "turn1_base.txt"),
            "policy": C.sha256_file(C.PROMPTS / POLICY_FILE[cell]), "v2_turn2": C.sha256_file(C.V2_PROMPTS / "turn2.txt")}
