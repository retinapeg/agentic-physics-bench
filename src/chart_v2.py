"""Draw results/v2/chart_<split>.svg from results/v2/summary_<split>.json (stdlib only; no model calls).

Usage (repo root): python3 src/chart_v2.py [dev|scored]
Grouped bars: proportion of episodes correct per difficulty group and
condition, with the count on every bar and the tool-request / compliance counts
under the tool conditions. Palette: dataviz reference categorical slots 1-3
(validated all-pairs in light and dark mode); slot 3 sits below 3:1 on the light
surface, so every bar carries a visible label. results/v2/summary_<split>.md is
the table view.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 760, 440
L, R, T, B = 64, 24, 118, 84
CONDITIONS = ("no_tool", "optional_tool", "required_tool")
LABELS = {"no_tool": "no tool", "optional_tool": "optional tool", "required_tool": "required tool"}
GROUPS = ("easy", "moderate", "hard")


def y(v):
    return T + (H - T - B) * (1 - v)


def main(split):
    s = json.loads((ROOT / "results" / "v2" / f"summary_{split}.json").read_text())
    n_planned = s["planned_episodes"]
    step = (W - L - R) / len(GROUPS)
    bar_w, gap = 44, 6
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-labelledby="t d" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
           f'<title id="t">V2 ({split}): proportion correct by difficulty group and tool condition</title>',
           f'<desc id="d">{s["attempted"]} of {n_planned} planned episodes attempted; {s["valid"]} valid. '
           'Bars show correct episodes divided by planned episodes per group and condition; the label on each bar '
           'is the count. Under the optional-tool bars: requests and executions; under the required-tool bars: compliant episodes.</desc>',
           '<style>',
           ':root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a}',
           '@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;--grid:#3a3a37;'
           '--s1:#3987e5;--s2:#d95926;--s3:#199e70}}',
           'text{fill:var(--ink2);font-size:12px}.h{fill:var(--ink);font-size:16px;font-weight:600}.sub{font-size:12.5px}',
           '.g{stroke:var(--grid);stroke-width:1}.b1{fill:var(--s1)}.b2{fill:var(--s2)}.b3{fill:var(--s3)}',
           '.lab{fill:var(--ink);font-size:11.5px;font-weight:600}.small{font-size:10.5px}',
           '</style>',
           f'<rect width="{W}" height="{H}" fill="var(--surface)"/>']
    cond_all = s["conditions"]
    head = ", ".join(f'{LABELS[c]} {cond_all[c]["correct"]}/{cond_all[c]["of_planned"]}' for c in CONDITIONS)
    out += [f'<text class="h" x="{L}" y="28">Correct episodes by difficulty and tool condition ({split} split)</text>',
            f'<text class="sub" x="{L}" y="48">Claude Code CLI, claude-opus-5, effort high; ±0.01 m/s² of the least-squares '
            f'slope; final answer after two turns. All groups: {head}.</text>',
            f'<text class="sub" x="{L}" y="66">Optional tool requested {cond_all["optional_tool"]["tool"]["requested"]}/'
            f'{cond_all["optional_tool"]["valid"]} valid episodes; required-tool compliance '
            f'{cond_all["required_tool"].get("required_compliant", 0)}/{cond_all["required_tool"].get("required_compliant_of_valid", 0)}. '
            f'{s["attempted"]}/{n_planned} planned episodes attempted.</text>',
            f'<text class="sub" x="{L}" y="84">A deterministic least-squares solver scores {s["deterministic_solver"]["correct"]}/'
            f'{s["deterministic_solver"]["of_tasks"]} tasks with zero error.</text>']
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        out.append(f'<line class="g" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        out.append(f'<text x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.2f}</text>')
    for gi, g in enumerate(GROUPS):
        cx = L + step * (gi + 0.5)
        p = s["groups"][g]["parameters"]
        out.append(f'<text x="{cx:.1f}" y="{H - B + 22}" text-anchor="middle" style="fill:var(--ink)">{g}</text>')
        out.append(f'<text class="small" x="{cx:.1f}" y="{H - B + 38}" text-anchor="middle">'
                   f'{p["n"]} points, {"uniform" if p["jitter"] == 0 else "irregular"} grid, σ = {p["sigma"]} m/s</text>')
        for ci, c in enumerate(CONDITIONS):
            x = cell = s["groups"][g]["conditions"][c]
            prop = x["proportion"] or 0.0
            bx = cx + (ci - 1) * (bar_w + gap) - bar_w / 2
            top = y(prop)
            tip = (f'<title>{g} / {LABELS[c]}: {x["correct"]}/{x["of_planned"]} correct; requested {x["tool"]["requested"]}, '
                   f'executed {x["tool"]["executed"]}; median |error| {x["abs_error_m_per_s2"]["median"]}</title>')
            if prop > 0:
                out.append(f'<path class="b{ci + 1}" d="M{bx:.1f} {y(0):.1f}V{top + 4:.1f}a4 4 0 0 1 4 -4h{bar_w - 8}'
                           f'a4 4 0 0 1 4 4V{y(0):.1f}Z">{tip}</path>')
            else:
                out.append(f'<rect class="b{ci + 1}" x="{bx:.1f}" y="{y(0) - 2:.1f}" width="{bar_w}" height="2">{tip}</rect>')
            out.append(f'<text class="lab" x="{bx + bar_w / 2:.1f}" y="{top - 6:.1f}" text-anchor="middle">'
                       f'{x["correct"]}/{x["of_planned"]}</text>')
            if c != "no_tool":
                sub = f'req {x["tool"]["requested"]} · exec {x["tool"]["executed"]}'
                if c == "required_tool":
                    sub = f'comply {x.get("required_compliant", 0)}/{x.get("required_compliant_of_valid", 0)}'
                out.append(f'<text class="small" x="{bx + bar_w / 2:.1f}" y="{y(0) + 14:.1f}" text-anchor="middle">{sub}</text>')
    ly = T - 14
    for ci, c in enumerate(CONDITIONS):
        lx = W - R - 330 + ci * 115
        out.append(f'<rect class="b{ci + 1}" x="{lx}" y="{ly - 9}" width="12" height="12" rx="2"/>')
        out.append(f'<text x="{lx + 17}" y="{ly + 1}">{LABELS[c]}</text>')
    out += [f'<text x="{L - 48}" y="{T - 10}">correct</text>',
            f'<text x="{(L + W - R) / 2:.0f}" y="{H - 14}" text-anchor="middle">difficulty group</text>', '</svg>']
    (ROOT / "results" / "v2" / f"chart_{split}.svg").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "scored")
