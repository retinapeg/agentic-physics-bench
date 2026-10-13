# Historical status

**The tool-use study (V1 and V2) is complete and frozen.** This repository preserves those two experiments with their protocols, frozen inputs, episode records, audits and analysis code. No further runs, calibration or protocol changes will be made to V1 or V2.

> **Amendment, 2026-10-13.** The sentence above originally read "Agentic Physics Bench is a completed study … No further runs, calibration or protocol changes will be made here." Leo asked for one physics-evaluation repository to carry forward and delegated the choice; this repository was chosen (option (a) of decision 1 in [`experiments/v3_instruction_compliance/DESIGN_REVIEW.md`](../experiments/v3_instruction_compliance/DESIGN_REVIEW.md)). The freeze statements on this page therefore apply to V1 and V2 only. New experiments live under `experiments/<name>/` with their own protocol, freeze manifest, run identity, data and results, and may not modify anything listed under "What is frozen". The tag `tool-use-study-final` (`0189c4b`) marks the last commit of the two-experiment study. The amendment was written by Claude (Claude Code) on that instruction; reversing it is Leo's call.

## What is frozen

- **Result and input artifacts.** Everything under `results/` and `data/`, and the prompt templates under `prompts/`, must not be modified:
  - episode and attempt records
  - summaries and charts
  - archived development stages and their audits
  - tasks, keys, plans and freeze manifests

  Summaries and charts are regenerated from the episode records byte for byte; CI checks this.
- **Frozen code.** These modules are hashed in the freeze manifests:
  - V1: `src/tasks.py`, `tools.py`, `evaluate.py`, `models.py`, `agent.py`, `run.py`
  - V2: `src/*_v2.py`

  Their docstrings were edited after release. CI checks that each manifest matches its release tag and that the code is otherwise unchanged. A scored rerun would therefore start from the release tag, not from `main`.
- **Records.** The protocols (`EXPERIMENT.md`, `EXPERIMENT_V2.md`) and `RESEARCH_LOG.md` are historical records. Any future correction is recorded as a dated entry in `RESEARCH_LOG.md`.

## Experiments and versions

| Name | What it is | Git reference |
|---|---|---|
| V0 | working name of V1 before release (same experiment) | tag `v0-protocol-freeze` → `f504c57` (protocol frozen before scored inference) |
| V1 | easy tasks; direct answer vs optional `fit_line`; 24 held-out episodes | tag `v1.0.0` → `8d336d8` |
| V2, run `v2-run-1` | three difficulty groups × no / optional / required tool × 3 repetitions; 162 held-out episodes | tag `v2.0.0` → `6810683` (merge of PR #1) |
| V2 development stages 1–4 | calibration before the V2 freeze; stages 1–2 void (second model present) | `results/v2/dev_stage1/`–`dev_stage3/` and `results/v2/episodes_dev.jsonl` |
| Final documentation freeze | results manifest, headline check, methodology, this file; no result or frozen file changed | branch `freeze/tool-use-study`, based on `main` at `009d4c2`, merged 2026-09-27; tag `tool-use-study-final` → `0189c4b` (created 2026-10-13) marks the final commit of the study, after the documentation commits of 2026-10-06 |
| V3 (design stage) | instruction compliance and an epistemic-honesty arm on the quantum pendulum; a design review and its check scripts only; nothing approved, built or run | `experiments/v3_instruction_compliance/`; an earlier unreviewed draft on the branch `v3-forbidden-tool` (`085576b`) |

Not part of this study: the branch `research/analytical-physics`, an analytical-physics proposal that was never approved or run.

To identify the frozen state, use the release tag rather than a SHA written in this file: a file cannot record the hash of the commit that contains it. The commit history and `RESEARCH_LOG.md` record how the repository reached that state.

## Where further work goes

**Physics-evaluation experiments continue in this repository** (amendment of 2026-10-13, above), each in its own directory under `experiments/`. The first is V3, at the design stage: [`experiments/v3_instruction_compliance/`](../experiments/v3_instruction_compliance/).

General agent-reliability experiments (oversight of coding agents) continue in a separate repository, planned as `agent_reliability_lab`. As of 2026-09-27 it had not been created. *Update 2026-10-06: it exists at [github.com/retinapeg/agent_reliability_lab](https://github.com/retinapeg/agent_reliability_lab), with its first run recorded there.* Experiments in either place have their own protocols, freezes and run identities. They do not modify this repository's frozen files or reuse V1/V2 results as their own.

**Unpublished evidence.** The raw CLI traces behind V1 and V2 (447 files) are kept in a private archive, with the local working notes and a bundle of every git ref. Their SHA-256 values are published in [`evidence/raw_trace_sha256.txt`](evidence/raw_trace_sha256.txt), so a copy of the traces can be checked against this record. On 2026-10-13, at `0189c4b`, `src/headline_results.py` run with those traces present reported 0 mismatches.

The lessons that carry over are recorded here and in [`methodology.md`](methodology.md):

- verify every call's trace against the declared system (model identities, server-side tools, usage iterations, CLI version)
- keep invalid episodes in the denominator
- freeze and hash the protocol before scored inference
- keep development and held-out data apart
