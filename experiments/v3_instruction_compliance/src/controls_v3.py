"""Per-call runtime checks for V3, parameterised by the expected identities (PROTOCOL.md section 9).

summarize_call_v3 reduces one CLI event stream to reviewed, non-identifying fields. control_violations_v3
decides whether the call ran as the declared system. With v3_checks=False and the V2 model as expected,
it reproduces V2's violation strings exactly (the parity test), so V3's checks are V2's plus additions.

Why the additions: in V2 the hidden second model was a different model from the tested one, so a second
key in the usage report gave it away. In V3 the tested model is the one that advisor consulted, so that
key would not appear; and in reconnaissance for V3 a classifier refusal was answered by a different model
through a fallback. The checks therefore also require the expected model to be present and alone, one
turn, at most one usage iteration, no fallback event, and an unchanged tool and skill inventory.
"""
import hashlib

NORMAL_STOP = ("end_turn",)
REQUIRED_INIT = ("model", "tools", "mcp_servers", "claude_code_version")
REFUSAL_EVENTS = ("model_refusal_no_fallback", "model_refusal_fallback")


def _names(items):
    out = []
    for x in items or []:
        out.append(str(x.get("name")) if isinstance(x, dict) else str(x))
    return sorted(out)


def inventory_of(init_event):
    """What the CLI says is loaded, without paths: names of skills, plugins and agents; slash commands hashed."""
    slash = _names(init_event.get("slash_commands"))
    return {"skills": _names(init_event.get("skills")), "plugins": _names(init_event.get("plugins")),
            "agents": _names(init_event.get("agents")), "n_slash_commands": len(slash),
            "slash_commands_sha256": hashlib.sha256("\n".join(slash).encode()).hexdigest()}


def summarize_call_v3(call):
    s = {"init": None, "inventory": None, "assistant_models": [], "content_types": [], "tool_use_blocks": 0,
         "server_tool_uses": [], "system_subtypes": [], "refusal": None, "result": None, "result_text": None,
         "models_used": [], "canonical_models": [], "max_output_tokens": None, "iteration_types": [],
         "iteration_count": 0, "rate_limit": None, "usage_windows": None, "thinking_tokens": None,
         "result_matches_assistant_text": None}
    texts = []
    for e in call["events"]:
        kind, sub = e.get("type"), e.get("subtype")
        if kind == "system" and sub == "init":
            s["init"] = {k: e.get(k) for k in ("model", "tools", "mcp_servers", "claude_code_version", "apiKeySource",
                                               "permissionMode", "fast_mode_state")}
            s["inventory"] = inventory_of(e)
        elif kind == "system":
            s["system_subtypes"].append(sub)
            if sub in REFUSAL_EVENTS:
                s["refusal"] = {"event": sub, "original_model": e.get("original_model"),
                                "fallback_model": e.get("fallback_model"), "category": e.get("api_refusal_category")}
        elif kind == "assistant":
            msg = e.get("message", {})
            s["assistant_models"].append(msg.get("model"))
            for c in msg.get("content", []):
                s["content_types"].append(c.get("type"))
                if c.get("type") == "text":
                    texts.append(str(c.get("text")))
                if c.get("type") == "tool_use":
                    s["tool_use_blocks"] += 1
                elif c.get("type") == "server_tool_use":
                    s["server_tool_uses"].append(str(c.get("name")))
                elif c.get("type") == "advisor_tool_result":      # the advisor's result block carries no name
                    s["server_tool_uses"].append("advisor")
        elif kind == "rate_limit_event":
            info = e.get("rate_limit_info") or {}
            s["rate_limit"] = {k: info.get(k) for k in ("status", "overageStatus", "isUsingOverage")}
            s["usage_windows"] = {k: (v or {}).get("utilization") for k, v in (info.get("unifiedWindows") or {}).items()}
        elif kind == "result":
            usage = e.get("usage") or {}
            model_usage = e.get("modelUsage") or {}
            stats = e.get("subagent_stats") or {}
            iterations = usage.get("iterations") or []
            s["result_text"] = e.get("result")
            s["thinking_tokens"] = (usage.get("output_tokens_details") or {}).get("thinking_tokens")
            s["models_used"] = sorted(model_usage)
            s["canonical_models"] = sorted({str(v.get("canonicalModel")) for v in model_usage.values()})
            s["max_output_tokens"] = sorted({v.get("maxOutputTokens") for v in model_usage.values() if v.get("maxOutputTokens")})
            s["iteration_types"] = sorted({str(i.get("type")) for i in iterations})
            s["iteration_count"] = len(iterations)
            s["result"] = {
                "subtype": sub, "is_error": e.get("is_error"), "num_turns": e.get("num_turns"),
                "stop_reason": e.get("stop_reason"), "terminal_reason": e.get("terminal_reason"),
                "duration_ms": e.get("duration_ms"), "api_error_status": e.get("api_error_status"),
                "n_permission_denials": len(e.get("permission_denials") or []), "safety_stops": e.get("safety_stops"),
                "fast_mode_state": e.get("fast_mode_state"), "subagents_spawned": stats.get("spawned"),
                "subagents_by_type": stats.get("by_type"),
                "reported_input_tokens": sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                                          "cache_read_input_tokens")),
                "output_tokens": usage.get("output_tokens"), "list_price_estimate_usd": e.get("total_cost_usd")}
    if s["result_text"] is not None and texts:
        # Recorded, not enforced: the graded text should be exactly what the assistant message carried. A
        # background post-turn summary (system event post_turn_summary) is written after the reply.
        got = s["result_text"].strip()
        s["result_matches_assistant_text"] = got in (texts[-1].strip(), "".join(texts).strip())
    return s


def is_refused(summary):
    """A safety-classifier refusal with fallback disabled: an outcome of the system under test, not a model switch."""
    result = summary["result"] or {}
    return (summary["refusal"] or {}).get("event") == "model_refusal_no_fallback" or result.get("stop_reason") == "refusal"


def is_truncated(summary):
    result = summary["result"]
    if result is None or is_refused(summary) or result.get("is_error"):
        return False
    return result.get("stop_reason") is not None and result.get("stop_reason") not in NORMAL_STOP


def control_violations_v3(call, summary, expected_model, expected_cli_version, expected_inventory=None, v3_checks=True):
    """Return the list of violated controls for one call (empty list = the call ran as declared)."""
    timed_out = call["returncode"] is None
    refused = v3_checks and is_refused(summary)
    v = []
    init = summary["init"]
    # --- V1's checks, in V1's order -------------------------------------------------------------------
    if init is None:
        if not timed_out:
            v.append("missing_init")
    else:
        missing = [k for k in REQUIRED_INIT if init.get(k) is None]
        if missing and not timed_out:
            v.append("missing_init_fields:" + ",".join(missing))
        if init.get("tools") != []:
            v.append("native_tools_present")
        if init.get("mcp_servers") != []:
            v.append("mcp_servers_present")
        if init.get("model") != expected_model:
            v.append("unexpected_model")
    if summary["tool_use_blocks"]:
        v.append("native_tool_use")
    assistant = [m for m in summary["assistant_models"] if not (refused and m == "<synthetic>")]
    if any(m != expected_model for m in assistant):
        v.append("unexpected_assistant_model")
    if (summary["rate_limit"] or {}).get("isUsingOverage"):
        v.append("overage_used")
    if call["stderr"].strip() and not timed_out:      # a timeout's synthetic stderr is not a CLI warning
        v.append("stderr_warning")
    # --- V2's additions, in V2's order ----------------------------------------------------------------
    if init and init.get("claude_code_version") != expected_cli_version:
        v.append("cli_version_mismatch")
    if summary["server_tool_uses"]:
        v.append("server_tool_use:" + ",".join(sorted(set(summary["server_tool_uses"]))))
    extra = sorted(m for m in summary["models_used"] if m != expected_model)
    if extra:
        v.append("unexpected_model_usage:" + ",".join(extra))
    odd = sorted(t for t in summary["iteration_types"] if t != "message")
    if odd:
        v.append("unexpected_iteration:" + ",".join(odd))
    if not v3_checks:
        return v
    # --- V3's additions -------------------------------------------------------------------------------
    result = summary["result"]
    if (summary["refusal"] or {}).get("event") == "model_refusal_fallback":
        v.append("model_refusal_fallback:" + str(summary["refusal"].get("fallback_model")))
    if init and init.get("fast_mode_state") != "off":
        v.append("fast_mode_not_off:" + str(init.get("fast_mode_state")))
    if expected_inventory is not None and init and summary["inventory"] != expected_inventory:
        v.append("inventory_changed")
    if summary["iteration_count"] > 1:
        v.append(f"iteration_count:{summary['iteration_count']}")
    if summary["canonical_models"] and summary["canonical_models"] != [expected_model]:
        v.append("unexpected_canonical_model:" + ",".join(summary["canonical_models"]))
    if result is None:
        if not timed_out:
            v.append("missing_result")
        return v
    if result.get("fast_mode_state") != "off":
        v.append("fast_mode_not_off:" + str(result.get("fast_mode_state")))
    if result.get("n_permission_denials"):
        v.append("permission_denials")
    if result.get("subagents_spawned") or result.get("subagents_by_type"):
        v.append("subagents_spawned")
    if refused:
        return v                                       # the rest are failures a refusal produces by construction
    if expected_model not in summary["models_used"]:
        v.append("missing_expected_model_usage")
    if result.get("num_turns") != 1:
        v.append(f"unexpected_num_turns:{result.get('num_turns')}")
    if result.get("api_error_status") is not None:
        v.append(f"api_error_status:{result.get('api_error_status')}")
    if result.get("is_error") or call["returncode"] not in (0, None):
        v.append("cli_error")
    return v
