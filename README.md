# Agentic Physics Bench

**Six studies, September to November 2026, of how LLM agents use, avoid and are audited around a numerical tool:** frozen protocols, deterministic grading and per-call trace audits. V1–V2 are a completed, frozen study; V3–V6 extend it to instruction compliance, adversarial disclosure and prohibited tools under rising workload ([the six studies](#the-six-studies)).

**V1–V2.** Does giving a model a tool change how it solves a problem, not just whether it gets the answer right? And can the trace prove that the system scored was the system declared?

**Result:** Correctness hit the ceiling in every condition (54/54 with no tool, an optional tool and a required tool), so the score separated nothing. A per-call trace audit during development found that a server-side advisor pathway in the Claude Code CLI had been active in 31 of 48 unique calls across two development stages, all made with the CLI's tools switched off (a second model, `claude-fable-5-1`, appears in the usage report of 28 of them). Those two stages were voided, the pathway was disabled, per-call checks were added, and the scored run that followed was clean: all 324 held-out calls show `claude-opus-5` alone.

**Why it matters:** Correct outputs alone did not prove that the declared system was the one being evaluated. The harness's existing controls passed the contaminated calls, because the second model appeared only in usage metadata. Aggregate scoring hid a measurement problem that only the traces exposed.

**Status:** V1 and V2 are complete and frozen (tag `tool-use-study-final`). V3–V6 live under [`experiments/`](experiments/), each with its own protocol, freeze, results and status (table below). Separate work on oversight of coding agents is in [agent_reliability_lab](https://github.com/retinapeg/agent_reliability_lab).

- Claude (`claude-opus-5`, via the Claude Code CLI) fits a line to small physics data tables under three tool policies. In V2, every call's trace is checked against the declared setup: model identities, server-side tools, the per-call usage report and CLI version (V1's per-call checks covered native tool use and message model IDs; its 24 traces were rescanned at the freeze and show `claude-opus-5` alone).
- Optional-tool use flipped from 0/12 in V1 (12 tasks, one episode each) to 54/54 in V2 (18 tasks × 3 repetitions) with no difference in correctness. The design cannot say why: the CLI version, prompt wording, advisor setting (not disabled in V1, explicitly disabled in V2; neither scored run shows a second model), turn structure and tasks all changed between the runs.
- One model, one synthetic task family, and tasks too easy to separate the conditions on accuracy. The study measures how reliably an LLM system performs a specified calculation, not whether an LLM is needed for it.

## The six studies

| Study | When | Question | State | What it found |
|---|---|---|---|---|
| V1 | Sep 2026 | Does Claude use an optional `fit_line` tool on easy line-fitting tasks? | Frozen (`v1.0.0`) | 12/12 correct with and without the tool; the optional tool was requested 0/12 times |
| V2 | Sep 2026 | The same question under no-tool, optional and required policies, with every call's trace audited | Frozen (`tool-use-study-final`) | 54/54 in every condition. A hidden advisor model ran in 31 of 48 development calls; those stages were voided and all 324 scored calls are clean |
| [V3](experiments/v3_instruction_compliance/) | Oct 2026 | When told not to use the tool, does the system comply? Does it claim an exact closed form for a quantum-pendulum kernel where none is known? | Protocol frozen; 36-call pilot on development items; held-out run not started | Before any task call, the CLI answered 4 of 6 trivial calls from a different model and reported success, and the launcher's environment leaked into the system under test. V3 now disables fallback, passes an allow-listed environment and treats a substituted model as an invalid call |
| [V4](experiments/v4_knowledge_vault/) | Oct 2026 | Knowledge Vault: can an attacker model get a secret out of a defender model, and what do the defences cost in useful work? | Development: deterministic baselines and one live four-call conversation | A deterministic judge scores disclosure, inference, policy leakage and utility separately; the permitted-output family shows a policy that leaks even under perfect enforcement |
| [V5](experiments/v5_tool_difficulty/) | Nov 2026 | Is a forbidden but working tool requested more as the workload grows? Two models (`gpt-6.1-sol`, `gpt-6-astra`) through the Codex CLI | Bounded 52-episode pilot | No request for the forbidden tool in 11 resolved decisions (5 more timed out); with the tool allowed, 16/16 solved; with no tool, 4/16 |
| [V6](experiments/v6_instruction_strength/) | Nov 2026 | Three prohibition wordings (soft, medium, firm) crossed with four workloads | Sealed 80-episode study; [report](reports/v6-instruction-strength-2026-11-03.pdf) | No request for the forbidden tool in 48 episodes (27 resolved decisions, 21 timed out); with the tool allowed, 16/16 solved. No evidence that softer wording or harder tasks raised violations; with two seeds per cell this is not an equivalence claim |

Each study's protocol states its limits; the V5 and V6 reports are in [`reports/`](reports/), with source hashes.

## Evidence (V1–V2)

| Claim | Where to check |
|---|---|
| 54/54 in each of three conditions, 162 episodes, 324 calls, 0 invalid | [`results/v2/summary_scored.md`](results/v2/summary_scored.md), [`results/v2/summary_scored.json`](results/v2/summary_scored.json) |
| Advisor active in 31 of 48 unique development calls (21 of 24 episodes; the two stage audits report 24/36 and 25/36 with 12 calls shared) | [`results/v2/dev_stage1/`](results/v2/dev_stage1), [`results/v2/dev_stage2/`](results/v2/dev_stage2) (`advisor_audit.json` in each) |
| Per-call checks: model identity, server-side tool blocks, non-message usage iterations, CLI version | `v2_control_violations` in [`src/run_v2.py`](src/run_v2.py); tests in [`tests/test_v2_run.py`](tests/test_v2_run.py) |
| Advisor disabled for the held-out run | `env_controls` in [`data/v2/freeze_manifest.json`](data/v2/freeze_manifest.json) and in every scored episode record |
| V1: 12/12 both conditions, tool requested 0/12 | [`results/summary.md`](results/summary.md) |
| Every number above recomputed from committed files | [`src/headline_results.py`](src/headline_results.py) (exits non-zero on any mismatch) |

What can and cannot be checked without the unpublished raw traces is set out in [`results/RESULTS_MANIFEST.md`](results/RESULTS_MANIFEST.md).

## Reproduce the analysis

Python 3.11, standard library only, no model calls:

```bash
python3 -m unittest discover -s tests      # 93 offline tests
python3 src/headline_results.py            # recomputes every headline number; 0 mismatches expected
```

Regenerating the summaries and charts byte-for-byte, and the CI freeze check against the release tags, are described in [docs/GUIDE.md](docs/GUIDE.md#reproduce-the-analysis).

## What V1–V2 do not show

- Any effect of tool access on accuracy. Every condition was at the ceiling; the paired bootstrap intervals are [0, 0]. That describes these data; it is not evidence that the conditions are equivalent.
- Why optional-tool uptake went from 0/12 to 54/54. Several things changed at once between V1 and V2.
- Anything about the provider's intent. The advisor finding is about harness controls: what "no tools" had to be verified against in that CLI version.
- Anything beyond one model behind one CLI, one family of synthetic line-fitting tasks and small held-out sets (12 and 18 tasks).

## Documentation

- [docs/GUIDE.md](docs/GUIDE.md): full findings, experiment design, results tables, episode flow diagram, repository map
- [docs/methodology.md](docs/methodology.md): design, controls, exclusion rules, statistics, supported and unsupported conclusions
- [docs/HISTORICAL_STATUS.md](docs/HISTORICAL_STATUS.md): what is frozen, tags, where further work goes
- [experiments/v3_instruction_compliance/](experiments/v3_instruction_compliance/): V3 (protocol frozen, pilot run on development items, held-out run not started)
- [experiments/v4_knowledge_vault/](experiments/v4_knowledge_vault/): V4, the adversarial Knowledge Vault lab and its local dashboard
- [experiments/v5_tool_difficulty/](experiments/v5_tool_difficulty/), [experiments/v6_instruction_strength/](experiments/v6_instruction_strength/): V5 and V6 protocols, code and results
- [reports/](reports/): V5 development and V6 instruction-strength reports, and the historical-evidence PDF, each with SHA-256 sums
- [EXPERIMENT.md](EXPERIMENT.md), [EXPERIMENT_V2.md](EXPERIMENT_V2.md): the frozen protocols
- [RESEARCH_LOG.md](RESEARCH_LOG.md): dated chronology of decisions, runs and corrections

Leo (@retinapeg) set the questions, made the design and protocol decisions and approved each freeze. The code, tests and documentation were written by Claude (Claude Code) at his direction, with a separate code review before each freeze and a multi-agent review during V2, both recorded in `RESEARCH_LOG.md`.
