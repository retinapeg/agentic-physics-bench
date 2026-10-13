"""Draw figures/requests_<split>.svg from results/summary_<split>.json (standard library only; no model calls).

Usage (repository root): python3 experiments/v3_instruction_compliance/figures/chart_v3.py [dev|heldout]
Left panel: turn-1 fit_line requests per policy cell, split by stratum, with the count on every bar.
Right panel: median seconds of the turn-1 call per cell on the 120-point tasks, with the median
CLI-reported thinking tokens under each bar. This script is not part of the frozen protocol: it only
renders numbers that analyze_v3.py computed. Palette and light/dark handling follow src/chart_v2.py.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
W, H = 860, 430
T, B = 112, 92
CELLS = ("A", "B", "C_YES", "C_NO", "D")
NAMES = {"A": ("A", "no policy"), "B": ("B", "try not to"), "C_YES": ("C: YES", "permitted"), "C_NO": ("C: NO", "prohibited"),
         "D": ("D", "do not")}
SPLITS = {"dev": "pilot, development tasks", "heldout": "held-out tasks"}


def main(split):
    s = json.loads((EXP / "results" / f"summary_{split}.json").read_text())["arm_a"]
    strata = s["by_stratum"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-labelledby="t d" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
           f'<title id="t">V3 Arm A ({SPLITS[split]}): tool requests and turn-1 time by policy cell</title>',
           f'<desc id="d">{s["valid"]} valid of {s["planned_episodes"]} planned episodes. Left: episodes whose first reply '
           'requested fit_line, per policy cell and stratum. Right: median seconds of the first call on 120-point tasks.</desc>',
           '<style>',
           ':root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--s1:#2a78d6;--s2:#eb6834}',
           '@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;--grid:#3a3a37;'
           '--s1:#3987e5;--s2:#d95926}}',
           'text{fill:var(--ink2);font-size:12px}.h{fill:var(--ink);font-size:16px;font-weight:600}.sub{font-size:12.5px}',
           '.p{fill:var(--ink);font-size:13px;font-weight:600}.g{stroke:var(--grid);stroke-width:1}.b1{fill:var(--s1)}.b2{fill:var(--s2)}',
           '.lab{fill:var(--ink);font-size:11.5px;font-weight:600}.small{font-size:10.5px}',
           '</style>',
           f'<rect width="{W}" height="{H}" fill="var(--surface)"/>',
           f'<text class="h" x="24" y="28">Does a policy sentence stop the tool request? ({SPLITS[split]})</text>',
           f'<text class="sub" x="24" y="48">claude-fable-5-1 through the Claude Code CLI, effort high. {s["valid"]} valid of '
           f'{s["planned_episodes"]} planned episodes; {s["model_calls"]} calls. The tool is described in every cell;</text>',
           '<text class="sub" x="24" y="64">one policy sentence differs. Cells C (permission NO) and D prohibit the request. '
           + ("Three tasks, one repetition: descriptive only." if split == "dev" else "") + '</text>']

    def panel(x0, width, title, top):
        out.append(f'<text class="p" x="{x0}" y="{T - 22}">{title}</text>')
        for i in range(5):
            v = top * i / 4
            yy = T + (H - T - B) * (1 - i / 4)
            out.append(f'<line class="g" x1="{x0}" x2="{x0 + width}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
            out.append(f'<text x="{x0 - 6}" y="{yy + 4:.1f}" text-anchor="end">{v:g}</text>')

    def bar(x, w, frac, cls):
        h = (H - T - B) * frac
        out.append(f'<rect class="{cls}" x="{x:.1f}" y="{H - B - h:.1f}" width="{w}" height="{max(h, 1.5):.1f}" rx="2"/>')
        return H - B - h

    # left: request share per cell and stratum
    x0, width = 56, 380
    panel(x0, width, "First reply requested fit_line (share of episodes)", 1)
    step = width / len(CELLS)
    for i, c in enumerate(CELLS):
        cx = x0 + step * (i + 0.5)
        for j, (st, cls) in enumerate((("S1", "b1"), ("S2", "b2"))):
            r = strata[st][c]["fit_line_request"]
            frac = r["x"] / r["n"] if r["n"] else 0
            bx = cx - 30 + j * 32
            top = bar(bx, 28, frac, cls)
            out.append(f'<text class="lab" x="{bx + 14:.1f}" y="{top - 5:.1f}" text-anchor="middle">{r["x"]}/{r["n"]}</text>')
        out.append(f'<text x="{cx:.1f}" y="{H - B + 17}" text-anchor="middle">{NAMES[c][0]}</text>')
        out.append(f'<text class="small" x="{cx:.1f}" y="{H - B + 31}" text-anchor="middle">{NAMES[c][1]}</text>')
    out += [f'<rect class="b1" x="{x0}" y="{H - 34}" width="11" height="11" rx="2"/>',
            f'<text x="{x0 + 16}" y="{H - 24}">10-point tasks</text>',
            f'<rect class="b2" x="{x0 + 118}" y="{H - 34}" width="11" height="11" rx="2"/>',
            f'<text x="{x0 + 134}" y="{H - 24}">120-point tasks</text>']

    # right: median turn-1 seconds on the 120-point tasks
    secs = {c: strata["S2"][c]["calls"]["turn1_median_elapsed_s"] for c in CELLS}
    think = {c: strata["S2"][c]["calls"]["turn1_median_thinking_tokens"] for c in CELLS}
    top_s = max(60, 60 * -(-max(v or 0 for v in secs.values()) // 60))
    x0, width = 504, 332
    panel(x0, width, "First call on 120-point tasks: median seconds", top_s)
    step = width / len(CELLS)
    for i, c in enumerate(CELLS):
        cx = x0 + step * (i + 0.5)
        v = secs[c] or 0
        top = bar(cx - 20, 40, v / top_s, "b2")
        out.append(f'<text class="lab" x="{cx:.1f}" y="{top - 5:.1f}" text-anchor="middle">{v:.0f} s</text>')
        out.append(f'<text x="{cx:.1f}" y="{H - B + 17}" text-anchor="middle">{NAMES[c][0]}</text>')
        tk = think[c]
        out.append(f'<text class="small" x="{cx:.1f}" y="{H - B + 31}" text-anchor="middle">{"—" if tk is None else f"{tk:,.0f}"}</text>')
    out.append(f'<text class="small" x="{x0}" y="{H - 24}">Under each bar: median CLI-reported thinking tokens of that call.</text>')
    out.append('</svg>')
    path = EXP / "figures" / f"requests_{split}.svg"
    path.write_text("\n".join(out) + "\n")
    print(path.relative_to(EXP.parents[1]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
