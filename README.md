# Agentic Physics Bench

I wanted to know whether giving a model a tool changes how it solves a problem, not just whether it gets the answer right.

**Result:** Accuracy hit the ceiling either way (54/54 in every condition), but a trace audit found that 31 of 48 "no-tool" development calls had quietly consulted a second model.

**Status:** Completed experiment, frozen September 2026. Follow-on work: `agent_reliability_lab` (not public yet).

- Claude, running through the Claude Code CLI, fits a line to small physics data tables with no tool, an optional tool or a required tool. Every call's trace is checked against the declared setup.
- The contaminated development runs were voided and per-call checks were added. All 324 held-out calls are clean. Optional-tool use also flipped, from 0/12 in V1 to 54/54 in V2.
- The study covers one model and one synthetic task family, and the tasks were too easy to separate the conditions on accuracy. The design can't say why tool use flipped.

[Technical details →](docs/GUIDE.md)
