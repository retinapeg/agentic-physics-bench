# Historical status

**Agentic Physics Bench is a completed study.** This repository preserves its two experiments, V1 and V2, with their protocols, frozen inputs, episode records, audits and analysis code. No further runs, calibration or protocol changes will be made here.

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
| Final documentation freeze | results manifest, headline check, methodology, this file; no result or frozen file changed | branch `freeze/tool-use-study`, based on `main` at `009d4c2`; the release tag chosen at merge identifies the final commit |

Not part of this study: the branch `research/analytical-physics`, an analytical-physics proposal that was never approved or run.

To identify the frozen state, use the release tag rather than a SHA written in this file: a file cannot record the hash of the commit that contains it. The commit history and `RESEARCH_LOG.md` record how the repository reached that state.

## Where further work goes

General agent-reliability experiments will continue in a separate repository, planned as `agent_reliability_lab`. As of 2026-09-27 it has not been created. Those experiments will have their own protocols, freezes and run identities. They will not modify this repository's frozen files or reuse its results as their own.

The lessons that carry over are recorded here and in [`methodology.md`](methodology.md):

- verify every call's trace against the declared system (model identities, server-side tools, usage iterations, CLI version)
- keep invalid episodes in the denominator
- freeze and hash the protocol before scored inference
- keep development and held-out data apart
