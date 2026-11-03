# Lineage

**Canonical home (Leo's one-repo decision, 2026-09-22 ~00:37 BST):** everything lives in https://github.com/retinapeg/agentic-physics-bench, local folder `~/Desktop/agentic-physics-bench`.
- **V1** is the immutable release: tag `v1.0.0`, commit `8d336d8302ecf76b6bcabf7afc37ab817a0630ea`, on `main`. Never move or overwrite the tag.
- **The analytical study** (pending approval) lives on the branch **`research/analytical-physics`**, which starts from `v1.0.0`.

History, recorded rather than rewritten:
1. **2026-09-21, 19:50–19:52:** at Leo's direction, Claude created a separate private repository, `retinapeg/agentic-physics-bench-analytic`, cloned from `v1.0.0`. Its one new commit, `955b3b2` (this lineage file, `PROPOSAL.md` and derived-project headers), was pushed there.
2. **2026-09-22, ~00:37:** Leo decided: "I don't want multiple repos having multiple versions of a project." Codex relayed the decision. Claude fetched `955b3b2` from the separate repository and started this branch from it, so the commit and its authorship are kept with the same hash. The follow-up documentation continues here.
3. **The separate repository is superseded.** It is preserved for now and not deleted, its history is not rewritten, and it is no longer used as a destination. Its local folder, `~/Desktop/agentic-physics-bench-analytic`, is also preserved as it was.

What the branch inherits from V1:
- the Claude CLI adapter (`src/models.py`);
- the bounded loop and validation pattern (`src/agent.py`, `src/tools.py`);
- enforced controls, freeze verification and the capped batch (`src/run.py`);
- deterministic grading, analysis, tests, and the logging and authorship conventions.

V1's data, results and traces describe V1 only. The study itself is in `PROPOSAL.md`, and nothing new has been run.
