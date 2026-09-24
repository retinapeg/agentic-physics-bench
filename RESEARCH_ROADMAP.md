# Research roadmap

> Update (2026-09-23): V1 was re-verified in an isolated checkout and recorded as complete (`RESEARCH_LOG.md`, "V1 verification"). **V2 (task difficulty × optional/required tool policy) has run:** 162 scored episodes, merged via PR #1 and tagged `v2.0.0` (see README and `EXPERIMENT_V2.md`). It supersedes follow-up 1 below (the extra-turn ablation is built into V2's design: two calls in every condition). A separate analytical study is proposed on the branch `research/analytical-physics` (its `PROPOSAL.md`); unapproved and unrun, not part of this branch. A control gap found in V2 development, a server-side CLI "advisor" consulting a second model, is documented in `EXPERIMENT_V2.md` section 6 and is now enforced against.

> Release note (2026-09-21): the pilot called "V0" below shipped as **V1** (tag `v1.0.0`). Leo chose the next extension: a derived project on numerical vs analytical performance with a bounded mathematical-tool harness, in a separate repository created from the V1 release. Follow-ups 1–3 below remain deferred.

Status as of 2026-09-21, after the V0 scored pilot (checkpoint 5). Written by Claude at Leo's direction from a research addendum that Codex drafted in chat. Leo supplied the addendum and directed its adoption (2026-09-21). Leo sets priorities. Nothing below is claimed as a result unless it appears under "Demonstrated".

## Demonstrated (with evidence)

- Reproducible development data with checked reference answers: `src/tasks.py`, `data/dev_*.jsonl`, `tests/test_tasks.py`. SHA-256 values are in `HANDOFF.md`.
- A working path from prompt to model, parser, grader and saved trace: `src/run.py`, `src/models.py`, `src/evaluate.py`.
- One correct direct-answer development episode on Claude (dev-01): `results/episodes_dev.jsonl`.
- A bounded tool workflow (`src/agent.py`, `src/tools.py`), tested offline on scripted replies. One real dev-01 workflow episode: the model answered without requesting the tool (correct, 1 call, 0 tool executions).
- **V0 scored pilot** (frozen protocol, tag `v0-protocol-freeze`; 12 cases × 2 conditions; Claude Code CLI 2.1.278, `claude-opus-5`, effort `high`):
  - direct 12/12 and workflow 12/12 correct; 12 paired ties;
  - tool requested in **0/12** workflow episodes;
  - all 24 answers equal the reference rounded to between 1 and 6 decimals;
  - 24 valid episodes, 24 invocations; no invalid runs or missing outputs.
  See `README.md` and `results/summary.md`.
- 36 offline checks pass, including regression tests for the two defects Codex reproduced.

## Not demonstrated

- That tool access improves accuracy or reliability. In V0 the optional tool was never requested, so no tool effect could be measured.
- That any harness architecture is better than another.
- Any accuracy estimate: one development case only checks that the pipeline works.
- Anything about GPT/Codex or local models, or about harder tasks.

## V0: remaining work (the current priority)

1. ~~A bounded `fit_line` tool workflow on dev-01.~~ Built; see `EXPERIMENT.md` sections 5–6.
2. ~~Approve the decisions, freeze the protocol and generate the 12 scored cases.~~ Done.
3. ~~Run both conditions on the same 12 cases with Claude.~~ Done. GPT is deferred until its controls are verified.
4. ~~Analysis, chart and README.~~ Done. Release decisions remain with Leo.

**Deterministic reference point.** `ls_slope` computes the answer exactly, so the task does not need a language model. V0 measures how reliably an LLM system performs a specified calculation: instruction following, output format, numerical accuracy and, in the tool condition, orchestration of a permitted tool. It cannot show that an LLM is necessary for least-squares regression. It also says nothing about long-horizon reasoning, self-improvement or novel architecture.

## Hypotheses (not results)

- **H1, tested by V0:** access to `fit_line` increases the number of correct answers compared with a direct answer. **Outcome: not testable in V0.** Both conditions scored 12/12 and the optional tool was never requested (ceiling). A useful test needs a task where direct answers fail, or a design that separates tool choice from tool use. The extra-turn confound (follow-up 1) remains.
- **H2, later extension, not tested:** harness components can become unnecessary, or even harmful, as models change ("harness debt"). Testing it means repeating a well-defined comparison across model versions while treating capability, task difficulty and inference budget carefully. Novelty is not established; a focused literature review comes first.

## Follow-up experiments (deferred until V0 is complete)

| # | Question | Smallest useful comparison | What must be controlled |
|---|---|---|---|
| 1 | Is a tool benefit just extra inference? | Two-turn condition without a calculator vs two-turn condition with `fit_line` (an ablation) | Comparable turn and token limits; report actual usage |
| 2 | Does structured checkpointing help recovery? | On a genuinely multi-step scientific task, inject the same interruption, then compare restarting with resuming from a structured checkpoint | Identical interruption point; idempotency (no duplicated side effects); a task where state actually matters |
| 3 | When does memory help, and when does it go stale? | Tasks where an earlier calibration or constraint matters and sometimes changes: no memory vs structured facts vs retrieved history | Separate retrieval success from correct use; stale-fact cases; cost of memory operations. Needs a new task design, because line fitting has no memory dependence |

## Sources

Read by Claude on 2026-09-21. For the preprints, only the arXiv abstract pages were read, not the full papers. We have not reproduced any of these findings.

**1. Martin, Cemaj & Cohen, "Scaling Managed Agents: Decoupling the brain from the hands." Anthropic Engineering blog, 8 April 2026.** Engineering account, not peer-reviewed. https://www.anthropic.com/engineering/managed-agents
- Claim: harnesses encode assumptions that go stale as models improve. Context resets added for one model became unnecessary with a later model. The authors separate the model-plus-harness, the tools and sandboxes, and durable session logs, so each can be changed independently.
- Evaluated: the reset example is described from experience, not measured systematically. Latency figures are given for the decoupled architecture (time-to-first-token reduced ~60% at p50, >90% at p95).
- Limitation: a single vendor's account of its own system, with no controlled comparison of task quality. The authors say they can't predict what future models will need.
- Relevance: every component in our harness should have a stated reason and a test that could show it is unnecessary. This motivates follow-up 1 and H2.

**2. Ben Sghaier, Li, Adams & Hassan, "Don't Blame the Large Language Model: How Agent Harness Evolution Shapes Coding Agent Quality." arXiv:2607.03691, v2 (v1 4 Jul 2026, v2 20 Jul 2026), cs.SE.** Preprint. https://arxiv.org/abs/2607.03691v2
- Claim: coding-agent quality changes are often caused by changes in the harness, not the model. The abstract says quality shifts are traced to specific pull requests and architectural components.
- Evaluated: 35 sequential Qwen Code CLI releases on 50 stratified SWE-bench Verified tasks, with the model held constant, measuring effectiveness and efficiency. It also examines five open-source harnesses more broadly.
- Limitation: the abstract names neither the fixed model nor any effect sizes. There is one harness in the controlled study, and the domain is software engineering, not science.
- Relevance: record CLI and harness versions alongside model IDs (our traces log `claude_code_version`). A score change can't automatically be blamed on the model.

**3. Mishra & Mishra, "When Does Memory Help? A Cost-Aware Evaluation of Long-Term Memory in Tool-Using LLM Agents." arXiv:2609.05441, v1 (26 Jul 2026), cs.AI.** Preprint. https://arxiv.org/abs/2609.05441
- Claim: recall benchmarks don't show whether remembered facts change what an agent does. Memory should be judged by task utility per unit cost.
- Evaluated: the MERIT benchmark, with episodic tool-use tasks in three domains, leak checks, controlled memory corruption and full token/dollar metering. Memory conditions compared include embedding retrieval, a structured fact store, summarisation, hybrids and full replay. Models: a preregistered 3-model × 3-seed grid plus a pilot and a spot-check. The abstract reports that agents acted on a correctly retrieved value only 55% of the time.
- Limitation: a preprint, so its numbers are the authors' claims. The domains aren't named in the abstract, and the results may depend on task design.
- Relevance: the design template for follow-up 3. Separate retrieval from correct use, include stale and corrupted facts, and report cost.
