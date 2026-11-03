# V5: forbidden tool use under increasing workload

This is a separate development extension of the existing `fit_line` experiment. See [PROTOCOL.md](PROTOCOL.md) for conditions, limits, denominators and uncertainty. V1–V4 evidence remains unchanged.

The numerical tool is executable even when the prompt forbids it. The harness records requests and actual invocations separately. Task difficulty is assigned before execution, with matched no-tool and allowed-tool conditions and a separate hidden-input necessary-tool calibration.

The entry point is `src/run_v5.py`; all results go to a fresh directory with a pre-call manifest, per-episode events and raw records, a summary, and SHA-256 checksums. `plan` previews the 52-episode design without inference. `run` explicitly launches a bounded development campaign. The small pilot cannot establish an empirically unsolved boundary or rank model compliance.

Historical evidence and its report are under `docs/evidence/2026-11-03/` and `reports/`. New V5 evidence must always be labelled separately.
