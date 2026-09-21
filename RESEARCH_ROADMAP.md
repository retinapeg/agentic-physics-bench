# Research roadmap

Status as of 2026-09-21 (commit `a9af5b1`). Drafted by Claude at Leo's direction, from a brief Leo supplied on 2026-09-21; the brief's drafter is not recorded here. Leo sets priorities. Nothing below is claimed as a result unless it appears under "Demonstrated".

## Demonstrated (with evidence)

- Reproducible development data with checked reference answers: `src/tasks.py`, `data/dev_*.jsonl`, `tests/test_tasks.py`. SHA-256 values are in `HANDOFF.md`.
- A working path from prompt to model, parser, grader and saved trace: `src/run.py`, `src/models.py`, `src/evaluate.py`.
- One correct direct-answer development episode on Claude (dev-01): `results/episodes_dev.jsonl`.
- 13 offline checks pass: `python3 -m unittest tests.test_ls_slope tests.test_tasks tests.test_evaluate`.

## Not demonstrated

- That tool access improves accuracy or reliability.
- That any harness architecture is better than another.
- Any accuracy estimate: one development case only checks that the pipeline works.
- Anything about GPT/Codex, local models, or scored cases.

## V0: remaining work (the current priority)

1. A bounded `fit_line` tool workflow on dev-01.
2. Freeze the protocol and generate the 12 scored cases.
3. Run direct and tool-workflow conditions on the same 12 cases with Claude; add GPT once its controls are verified.
4. Analysis from saved results: complete denominators, paired outcomes, failure review, one chart, a factual README with reproduction steps.

**Deterministic reference point.** `ls_slope` computes the answer exactly, so the task does not need a language model. V0 measures how reliably an LLM system performs a specified calculation: instruction following, output format, numerical accuracy and, in the tool condition, orchestration of a permitted tool. It cannot show that an LLM is necessary for least-squares regression. It also says nothing about long-horizon reasoning, self-improvement or novel architecture.

## Hypotheses (not results)

- **H1, tested by V0:** access to `fit_line` increases the number of correct answers compared with a direct answer. This is confounded: the workflow also gets an extra model turn (see follow-up 1).
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
