"""Draw results/chart.svg from results/summary.json (stdlib only; no model calls).

Usage (repo root): python3 src/chart.py
Palette: dataviz reference categorical slots 1-2, validated in light and dark
mode. Each point carries a <title> tooltip; results/summary.md is the table view.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 760, 400
L, R, T, B = 64, 24, 112, 56
YMAX = 12.0  # x 1e-3 m/s^2
TOL = 10.0   # the frozen tolerance, 0.01 m/s^2


def y(v):
    return T + (H - T - B) * (1 - v / YMAX)


def main():
    s = json.loads((ROOT / "results" / "summary.json").read_text())
    rows = s["episodes"]
    cases = sorted({r["case_id"] for r in rows})
    step = (W - L - R) / len(cases)
    x = {c: L + step * (i + 0.5) for i, c in enumerate(cases)}
    d, w = s["conditions"]["direct"], s["conditions"]["workflow"]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           'role="img" aria-labelledby="t d" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
           '<title id="t">Absolute error per scored case, direct vs tool workflow</title>',
           f'<desc id="d">All 24 answers were correct. Largest absolute error {max(r["abs_error"] for r in rows):.4f} '
           'm/s^2 against a tolerance of 0.01 m/s^2. The tool was requested in 0 of 12 workflow episodes.</desc>',
           '<style>',
           ':root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--s1:#2a78d6;--s2:#eb6834}',
           '@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;'
           '--grid:#3a3a37;--s1:#3987e5;--s2:#d95926}}',
           'text{fill:var(--ink2);font-size:12px}.h{fill:var(--ink);font-size:16px;font-weight:600}',
           '.sub{font-size:12.5px}.g{stroke:var(--grid);stroke-width:1}.tol{stroke:var(--ink2);stroke-width:1.5;'
           'stroke-dasharray:5 4}.d{fill:var(--s1);stroke:var(--surface);stroke-width:2}'
           '.w{fill:var(--s2);stroke:var(--surface);stroke-width:2}',
           '</style>',
           f'<rect width="{W}" height="{H}" fill="var(--surface)"/>',
           f'<text class="h" x="{L}" y="28">All 24 scored answers were correct, far inside the tolerance</text>',
           f'<text class="sub" x="{L}" y="48">|answer − reference slope| per case (×10⁻³ m/s²), Claude Code CLI, '
           'claude-opus-5.</text>',
           f'<text class="sub" x="{L}" y="66">Direct {d["correct"]}/12 and workflow {w["correct"]}/12 correct; '
           f'the optional tool was requested {w["tool_requested"]}/12 times.</text>',
           f'<text class="sub" x="{L}" y="84">A deterministic least-squares solver scores '
           f'{s["deterministic_solver"]["correct"]}/12 with zero error.</text>']
    for v in range(0, 13, 2):
        out.append(f'<line class="g" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        out.append(f'<text x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    out.append(f'<line class="tol" x1="{L}" x2="{W - R}" y1="{y(TOL):.1f}" y2="{y(TOL):.1f}"/>')
    out.append(f'<text x="{W - R}" y="{y(TOL) - 6:.1f}" text-anchor="end" style="fill:var(--ink)">'
               'tolerance 0.01 m/s² (10 × 10⁻³)</text>')
    for c in cases:
        out.append(f'<text x="{x[c]:.1f}" y="{H - B + 20}" text-anchor="middle">{c}</text>')
    for r in rows:
        v = r["abs_error"] * 1e3
        cx, cy = x[r["case_id"]] + (-6 if r["condition"] == "direct" else 6), y(v)
        tip = (f'<title>{r["case_id"]} {r["condition"]}: answer {r["answer"]}, reference {r["a_ref"]:.6f}, '
               f'|error| {r["abs_error"]:.2e} m/s² ({r["status"]})</title>')
        if r["condition"] == "direct":
            out.append(f'<circle class="d" cx="{cx:.1f}" cy="{cy:.1f}" r="5">{tip}</circle>')
        else:
            out.append(f'<path class="w" d="M{cx:.1f} {cy - 6:.1f}L{cx + 6:.1f} {cy:.1f}L{cx:.1f} {cy + 6:.1f}'
                       f'L{cx - 6:.1f} {cy:.1f}Z">{tip}</path>')
    ly = y(TOL) + 26
    out += [f'<circle class="d" cx="{W - R - 214}" cy="{ly - 4:.1f}" r="5"/>',
            f'<text x="{W - R - 204}" y="{ly:.1f}">direct answer</text>',
            f'<path class="w" d="M{W - R - 110} {ly - 10:.1f}L{W - R - 104} {ly - 4:.1f}L{W - R - 110} {ly + 2:.1f}'
            f'L{W - R - 116} {ly - 4:.1f}Z"/>',
            f'<text x="{W - R - 98}" y="{ly:.1f}">tool workflow</text>',
            f'<text x="{L - 48}" y="{T - 10}">×10⁻³</text>',
            f'<text x="{(L + W - R) / 2:.0f}" y="{H - 12}" text-anchor="middle">scored case</text>',
            '</svg>']
    (ROOT / "results" / "chart.svg").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
