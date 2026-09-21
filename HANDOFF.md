# Claude handoff — 2026-09-21

Leo owns the Agentic Physics Bench implementation. Follow `CLAUDE.md` and `WORKMODE.md`; Codex is the independent reviewer. This is setup work, not a completed benchmark.

## Verified setup

- Apple M1 with 8 GB RAM; Python 3.11.5 is available, with no project virtual environment yet.
- Claude Code 2.1.278 is signed in through a Claude subscription. The local `results/checkpoint0-claude.jsonl` trace records one no-tool `claude-opus-5` response, "Newton": the init tool list is empty, no tool calls occur, and the run completed. The trace reports no paid overage. Its USD cost field is a list-price estimate, not a bill.
- Codex CLI 0.154.0 is signed in through ChatGPT. The local `results/checkpoint0-codex.jsonl` trace records one response, "newton", with no tool events, from a request specifying `gpt-6-astra`. Codex JSONL does not expose the served model ID; record Astra as requested, not independently confirmed. The Codex credit balance was unchanged after this call.
- No provider API key was set in the checked shell. These were subscription-backed CLI smoke tests, not a scored experiment.
- No local model runtime or weights are installed. The original `gpt-oss-20b` target does not fit the 8 GB local-memory budget; a smaller open-weight model needs an explicit choice and live smoke test.

The two local raw smoke traces are ignored by Git because they contain session and machine metadata. Review any future trace before publishing it.

## Next with Leo

1. `EXPERIMENT.md` was not included in the starter pack. Write and review the protocol with Leo before freezing tasks or claiming results. The plan is four development cases, 12 scored cases, direct and bounded-tool conditions, and up to three model backends; none has been evaluated.
2. Set up the Python environment and a small local open-weight backend. Confirm every chosen backend with an actual response and recorded configuration before scored runs.
3. Treat subscription CLIs as agent systems with their own orchestration. A score difference across them is not automatically a raw-model effect. Record this limitation and any tool or context differences.
4. Leo writes the core code and `RESEARCH_LOG.md` lessons in his own words. Claude tutors one checkpoint at a time; Codex reviews. No public GitHub release or Twitter post has happened yet.
