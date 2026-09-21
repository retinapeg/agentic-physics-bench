# Lineage

This project is derived from **Agentic Physics Bench V1**.

| | |
|---|---|
| Parent repository | https://github.com/retinapeg/agentic-physics-bench |
| Parent release | tag `v1.0.0` |
| Release commit | `8d336d8302ecf76b6bcabf7afc37ab817a0630ea` |
| Derived on | 2026-09-21, by Claude at Leo's direction |
| How | `git clone` of the parent, `main` set to `v1.0.0`. The full parent history, including tags `v0-protocol-freeze` and `v1.0.0`, is kept |

- **Parent stays stable.** The `parent` git remote here is fetch-only (its push URL is disabled). Nothing in this project changes the shipped V1.
- **What is inherited:**
  - the Claude CLI adapter (`src/models.py`);
  - the bounded loop and validation pattern (`src/agent.py`, `src/tools.py`);
  - enforced controls, freeze verification and the capped batch (`src/run.py`);
  - deterministic grading (`src/evaluate.py`), analysis and chart scripts, tests, and the logging and authorship conventions.
- **Inherited results:** V1's results, data and traces are part of the history. They describe the parent study and are not results of this project.
- **What is new here:** a study of numerical vs analytical performance on matched physics problems, with a bounded mathematical-tool harness: restricted numerical calculation, symbolic differentiation and analytical-answer verification. See `PROPOSAL.md`. Nothing new has been run yet.
