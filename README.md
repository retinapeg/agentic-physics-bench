# Agentic Physics Bench

Does giving a model a tool change how it solves a problem, not just whether it gets the answer right? And can the trace prove that the system scored was the system declared?

**Result:** Correctness hit the ceiling in every condition (54/54 with no tool, an optional tool and a required tool), so the score separated nothing. A per-call trace audit during development found that a server-side advisor pathway in the Claude Code CLI had been active in 31 of 48 unique calls across two development stages, all made with the CLI's tools switched off (a second model, `claude-fable-5-1`, appears in the usage report of 28 of them). Those two stages were voided, the pathway was disabled, per-call checks were added, and the scored run that followed was clean: all 324 held-out calls show `claude-opus-5` alone.

**Why it matters:** Correct outputs alone did not prove that the declared system was the one being evaluated. The harness's existing controls passed the contaminated calls, because the second model appeared only in usage metadata. Aggregate scoring hid a measurement problem that only the traces exposed.

**Status:** Two completed experiments (V1 and V2), frozen September 2026. The follow-on work on agent oversight is in [agent_reliability_lab](https://github.com/retinapeg/agent_reliability_lab).

- Claude (`claude-opus-5`, via the Claude Code CLI) fits a line to small physics data tables under three tool policies. In V2, every call's trace is checked against the declared setup: model identities, server-side tools, the per-call usage report and CLI version (V1's per-call checks covered native tool use and message model IDs; its 24 traces were rescanned at the freeze and show `claude-opus-5` alone).
- Optional-tool use flipped from 0/12 in V1 (12 tasks, one episode each) to 54/54 in V2 (18 tasks × 3 repetitions) with no difference in correctness. The design cannot say why: the CLI version, prompt wording, advisor setting (not disabled in V1, explicitly disabled in V2; neither scored run shows a second model), turn structure and tasks all changed between the runs.
- One model, one synthetic task family, and tasks too easy to separate the conditions on accuracy. The study measures how reliably an LLM system performs a specified calculation, not whether an LLM is needed for it.

## Evidence

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

## What this does not show

- Any effect of tool access on accuracy. Every condition was at the ceiling; the paired bootstrap intervals are [0, 0]. That describes these data; it is not evidence that the conditions are equivalent.
- Why optional-tool uptake went from 0/12 to 54/54. Several things changed at once between V1 and V2.
- Anything about the provider's intent. The advisor finding is about harness controls: what "no tools" had to be verified against in that CLI version.
- Anything beyond one model behind one CLI, one family of synthetic line-fitting tasks and small held-out sets (12 and 18 tasks).

## Documentation

- [docs/GUIDE.md](docs/GUIDE.md): full findings, experiment design, results tables, episode flow diagram, repository map
- [docs/methodology.md](docs/methodology.md): design, controls, exclusion rules, statistics, supported and unsupported conclusions
- [docs/HISTORICAL_STATUS.md](docs/HISTORICAL_STATUS.md): what is frozen, tags, where further work goes
- [EXPERIMENT.md](EXPERIMENT.md), [EXPERIMENT_V2.md](EXPERIMENT_V2.md): the frozen protocols
- [RESEARCH_LOG.md](RESEARCH_LOG.md): dated chronology of decisions, runs and corrections

Leo (@retinapeg) set the questions, made the design and protocol decisions and approved each freeze. The code, tests and documentation were written by Claude (Claude Code) at his direction, with a separate code review before each freeze and a multi-agent review during V2, both recorded in `RESEARCH_LOG.md`.
