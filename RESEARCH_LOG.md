# AI research and engineering lessons

Append-only. Short evidence-backed entries, not copied chat transcripts. No medical details, private messages, credentials or employer data belong in the public log.

## Evidence status

PLANNED: not attempted.
OBSERVED: output or artifact exists; interpretation may still be uncertain.
VERIFIED: a named check reproduced the relevant result.
HYPOTHESIS: a possible explanation, not established fact.

Do not change an old mistaken claim silently. Add a dated correction with the new evidence.

## Entry template

### YYYY-MM-DD | checkpoint | short title
- Concept:
- What I expected:
- What I did / observed:
- Evidence: command + result, test name, file/line, commit, or run ID.
- Failure type and suspected cause, when applicable:
- Change and verification:
- Lesson in my own words:
- Status: PLANNED / OBSERVED / VERIFIED / HYPOTHESIS.
- Next experiment or remaining uncertainty:

Keep ordinary entries to five to eight lines; combine fields when possible.

## 2026-09-21 | Design | Separate expectation from evidence
- Concept: a hypothesis is not a measured result.
- What I expect: tools may reduce the open/frontier performance gap.
- Plan: freeze a small physics set and compare direct and bounded-tool conditions.
- Evidence: none yet; this starter pack contains no evaluated episodes.
- Lesson: publish the observed counts even if the hypothesis fails.
- Status: PLANNED.

## 2026-09-21 | 0 Environment | One-word answers, thousands of reported input tokens
- Authorship: Claude drafted this entry at 13:31 BST from the saved traces, after the smoke tests. Leo ran the Claude smoke test. Codex ran the GPT smoke test.
- Concept: a subscription CLI is an agent system (the model plus whatever instructions, tool definitions and context the CLI adds), not a bare model. Model identity has to come from provider metadata.
- Observed, Claude: Claude Code 2.1.278, run with `--tools ""` (per Leo). Trace init line: `model: claude-opus-5`, `tools: []`, `mcp_servers: []`, `apiKeySource: none`. Answer "Newton"; 1 turn; 1.66 s. Overage was rejected (`org_level_disabled`). The trace reports the 7-day usage window at 65% utilisation (trace file modified 11:41).
- Observed, Codex: Codex CLI 0.154.0, `gpt-6-astra` requested. Answer "newton"; no tool events. The JSONL has no field for the model that actually served the request.
- Reported input tokens: Claude 2 + 3,162 cache-write + 1,441 cache-read ≈ 4,605. Codex 16,297 (6,400 cached). How these split into hidden instructions, tool definitions and other context is unverified. Neither trace records the prompt text or the command line.
- Evidence: `results/checkpoint0-claude.jsonl` lines 0–3; `results/checkpoint0-codex.jsonl` `turn.completed.usage`. Both are gitignored and exist only on this machine.
- Lesson (Leo): TODO
- Status: OBSERVED. Why Codex reports about 3.5× Claude's input tokens is unknown. HYPOTHESIS: tool definitions and/or an AGENTS.md read from the working directory.

## 2026-09-21 | 1a Protocol | Grade the fit of the displayed data, not the generator
- Concept: reference answers and leakage. The answer key must depend only on what the model sees.
- Did: at Leo's request, Claude drafted a skeleton `EXPERIMENT.md` (DRAFT, untracked, every parameter marked DECIDE). Leo decided the section 3 parameters in chat:
  - seeds 101 (dev) and 202 (scored); N = 10; t = 0–4.5 s in 0.5 s steps;
  - `a_true` continuous in ±(0, 5] m/s², sign-balanced: 2+/2− dev, 6+/6− scored; v0 uniform in [−10, 10] m/s;
  - velocities shown to 2 decimal places, with the reference computed from the displayed values.
  - σ, the tolerance, and sections 5–7 are still open.
- Evidence: Sxx = 20.625 s² (supplied by Codex; Claude reran it in python3), so SD(a_ref about a_true) = σ/√20.625 ≈ 0.22σ. At the 1a check, `grep -n DECIDE EXPERIMENT.md` still showed all 7 section 3 rows as DECIDE, so the gate had not passed.
- Review notes (Claude):
  - Balancing the sign of `a_true` does not fix the sign of `a_ref` near zero. This needs a minimum |a_true| or a redraw rule.
  - The σ/tolerance check should be least-squares versus cheap shortcuts such as the endpoint slope, not guessing `a_true`. Leo's pushback on this was accepted.
- Explanation submitted in chat, assistant-drafted per Leo's correction (not independently written by Leo): "We should grade against `a_ref` because the model is asked to fit the displayed measurements. Noise and rounding can make that slope differ from `a_true`, so using `a_true` could mark a correct fit as incorrect."
- Lesson (Leo, own words): TODO (see LEARNING_REVIEW.md Q2).
- Status: OBSERVED (design decisions only; nothing measured). Codex tool control is unresolved: a read-only sandbox does not disable its tools.

## 2026-09-21 | Correction | Attribution, timestamps and token wording
- Recorded 18:14 BST by Claude at Leo's direction. Earlier text in the two entries above and in HANDOFF.md was fixed in place, because it was written earlier today (13:31) and never committed. This entry records what changed.
- Attribution:
  - Codex, not Leo, ran the GPT smoke test and did the initial HANDOFF, commit and GitHub setup.
  - Leo ran the Claude smoke test.
  - Codex supplied Sxx = 20.625 s²; Claude checked it. The earlier text said Leo derived it.
  - The 1a explanation was assistant-drafted; the earlier text presented it as Leo's own words.
- Timestamps taken from file modification times are now labelled "(mtime)". The git commit time is labelled "(git)".
- Token figures are now "reported input tokens". The earlier "hidden context/tokens" wording claimed a breakdown nobody has verified.
- Status: VERIFIED against Leo's statement in chat; no trace records who ran each command.

## 2026-09-21 | 1a Protocol | Section 3 recorded in the file
- Authorship: decisions by Leo; entered into `EXPERIMENT.md` by Claude at Leo's direction.
- Observed: all six choices are in the section 3 table. σ = 0.5 m/s is marked PROVISIONAL (development only). Two rows still contain DECIDE: the final σ and the minimum |a_true| or redraw rule. The protocol remains DRAFT.
- Evidence: `grep -n DECIDE EXPERIMENT.md` after the edit.
- Also: Claude drafted `LEARNING_REVIEW.md` (questions, marking scheme, tutor instructions) at Leo's request. Comprehension questions now live there; working-code checks stay in the checkpoints.
- Status: OBSERVED. 1a gate passed for the recorded choices; final σ, tolerance and the |a| floor are open.

## Topics to capture as they occur

Model vs agent vs pretrained weights; API/SDK vs model identity; benchmarks vs evals; reference validation; data leakage; prompts and configuration hashes; structured-output failures; tool dispatch and stopping; retries and missing denominators; retrieval vs generation errors; unsupported claims vs numerical mistakes; RAG vs fine-tuning; paired analysis; reproducibility; what I implemented vs delegated.
