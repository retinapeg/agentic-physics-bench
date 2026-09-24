# Workmode: LEARN_AND_SHIP

> **Superseded (2026-09-21, 18:35 BST).** Leo handed the implementation to Claude. Claude Code wrote all code, tests and documentation at Leo's direction; Leo set the research questions, made the design and protocol decisions, approved each freeze and published. The "human-owned implementation" line, the role allocation and the multi-model scope below are historical. Current provenance: [README](README.md#provenance) and [CLAUDE.md](CLAUDE.md).

## Outcome

Publish a small, reproducible physics-tool-use pilot and understand its central implementation. The public result is a completed experiment, not a collection of planned features.

**One repository. One frozen question. One shared agent loop. Human-owned implementation.**

The question is whether bounded numerical-tool access changes the gap between an open-weight model and frontier models on Leo's own physics cases. The actual experiment design is in EXPERIMENT.md.

Today is not the day to integrate the institutional workbench, train model weights, add Jev or other specialist models, construct a model-routing service, or build a web app.

## Role allocation

- Leo: research lead, physicist, implementer and publisher.
- Claude: tutor, next-action coach and explanations.
- Codex: independent adversarial reviewer.

Only Leo edits the core implementation by default. Keep the two AI sessions separate; share decisions through HANDOFF.md, not giant copied transcripts. Never let both helpers edit the same working tree concurrently.

The existing institutional workbench can remain unchanged. Do not run its autonomous build modes over the learner-owned core. Reuse the idea of independent review and bounded repair, not its whole execution machinery.

## Modes

LEARN: explain -> Leo implements -> test -> Leo explains -> log.
REVIEW: Codex checks the current artifact -> Leo repairs -> one recheck.
SHIP: freeze features -> reproduce results -> verify claims -> publish.

These are ordinary instructions, not claims that a global /workmode command exists. Leo selects a mode in plain language.

## Checkpoints

| Stage | Leo's action | Concept learned | Gate |
|---|---|---|---|
| 0. Environment and access | Inspect the terminal environment and make one real call to each proposed backend | Runtime, weights, endpoint, authentication, SDK, provider metadata | Record working backend, exact returned model ID and a response; no guessed access |
| 1. Ground truth | Implement four simple physics task families, fixed synthetic inputs and deterministic references | Benchmark design, development split, reference answers, units, leakage | Four development examples checked independently; 12 scored cases validated and frozen |
| 2. Direct baseline | Write one model adapter, structured answer parsing, grading and append-only run output | Inference, schemas, evaluations, experiment traces | One development episode goes input -> model -> parsed result -> grade -> trace |
| 3. Agent loop | Add a small tool registry, dispatch and bounded observation/action loop | Agency, tool schemas, state, errors, stopping | Development agent selects a tool; bad arguments and tool-limit paths are tested |
| 4. Frozen comparison | Smoke-test all adapters, freeze manifest, run the full selected matrix, score in pandas | Controlled system comparisons, denominators, paired changes, reproducibility | Every planned episode has an outcome; analysis reads saved results without new inference |
| 5. Evidence report | Reuse the same loop with read-only statistics and evidence tools | Retrieval, RAG, grounding, abstention | Every report number matches deterministic statistics and each example links to an actual run |
| 6. Release | Run tests, execute notebook from fresh kernel, inspect public files, tag and publish | Reproducibility, limitations, release checks | Clean public repo, real results, chart, readable README and evidence-based post |

After each stage, update RESEARCH_LOG.md and HANDOFF.md. Log the failure when a gate does not pass; do not label unfinished work as finished.

## Scope ceiling and cuts

Target: 12 scored cases x 3 models x 2 conditions = 72 episodes, plus four separate development cases. Agent episodes can contain several model calls.

Core fallback: the same 12 cases x 2 models x 2 conditions = 48 episodes, with at least one genuinely open-weight model and one frontier model. Drop the third provider only for documented access or implementation blockers, not because its scores are inconvenient. Prefer making this decision during smoke testing, before evaluation.

No increase above 12 scored cases today. The earlier 20-case target is intentionally reduced to prioritize reference validation and a finished learning build. More cases are a later version, not an unfinished V0 requirement.

When behind: stop optional model/provider work, semantic embeddings, extra metrics and cosmetic polish. Keep valid grading, the hand-written agent, complete logs and the release. The small evidence report reuses the existing loop; do not create a second agent framework. Should even that be blocked, ship the measured benchmark with a human-written report and state that the automated reporting component is deferred.

Reserve the last work block for release rather than a new feature. No overnight extension is a success criterion. Take normal food, movement and rest breaks; reduce scope rather than treating an 18-hour session as mandatory.

## Minimal implementation map

Suggested files to create as needed, not generated by this pack:

- src/tasks.py: synthetic inputs and reference generation.
- src/models.py: provider adapters and response normalization.
- src/agent.py: the single bounded loop.
- src/tools.py: allowlisted numerical tools and separate reporter tools.
- src/run.py: episode orchestration and raw trace persistence.
- src/evaluate.py: deterministic scoring and summary export.
- tests/: reference, parser, tool-boundary and stopping checks.
- data/: development/scored prompts and separate reference keys.
- results/: frozen manifest, episode traces, scores and report.
- notebooks/analysis.ipynb: executed, human-readable analysis.
- README.md: measured outcome, methods, limitations and reproduction.

Small helper functions can stay in these files. Do not add abstractions before they solve an observed problem.

## Future institutional-engineering connection

Use plain experiment fields such as model_id, condition, role, tool_policy, prompt_hash and step_count in traces. That is the entire integration cost today.

A later version can compare a single solver with a bounded solver/critic arrangement, holding the task set, model roster and aggregate inference budget as constant as practical. A further version can test specialist non-chat models for routing or verification. Neither is required for V0. Preserve the original benchmark version; use fresh held-out tasks when the published cases become development material.
