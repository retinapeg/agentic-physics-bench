"""Read-only historical projections. Never regenerate or change historical evidence."""
import functools
import json

import common

SOURCES = [
    ("V1 · scored", "results/episodes_scored.jsonl"),
    ("V2 · development 1", "results/v2/dev_stage1/episodes_dev.jsonl"),
    ("V2 · development 2", "results/v2/dev_stage2/episodes_dev.jsonl"),
    ("V2 · clean scored", "results/v2/episodes_scored.jsonl"),
    ("V3 · pilot / instruction", "experiments/v3_instruction_compliance/results/episodes_dev.jsonl"),
    ("V3 · pilot / pendulum", "experiments/v3_instruction_compliance/results/pendulum_episodes_dev.jsonl"),
]


@functools.lru_cache(maxsize=1)
def archive():
    audit = {}
    audit_sources = {}
    for stage in (1,2):
        source = f"results/v2/dev_stage{stage}/advisor_audit.json"
        doc = json.loads((common.REPO / source).read_text())
        for episode in doc["episodes"]:
            for call in episode["calls"]:
                key = (episode["episode_id"], call["turn"])
                audit[key] = call
                audit_sources.setdefault(key, []).append(source)
    runs, unique_dev, scored_calls = [], {}, []
    for group, path in SOURCES:
        for line, raw in enumerate((common.REPO / path).read_text().splitlines(), 1):
            row = json.loads(raw)
            rid = "history-" + common.digest([path, row["episode_id"]])[:16]
            events = []
            for t in row["turns"]:
                key = (row["episode_id"], t["turn"])
                audited = audit.get(key) if "development" in group else None
                provenance = dict(t.get("cli") or {})
                if audited:
                    provenance["models_used"] = audited["models_used"]
                    provenance["server_tool_uses"] = audited["server_tool_uses"]
                    unique_dev[key] = audited
                if group == "V2 · clean scored":
                    scored_calls.append(provenance)
                for actor, text in (("user", t.get("prompt")), ("defender", t.get("response_text"))):
                    if text is not None:
                        events.append({"seq":len(events)+1, "kind":"message", "actor":actor, "text":text,
                            "turn":t["turn"], "episode_started_at":row.get("started_at"), "flow":"historical",
                            "source":f"{path}:{line}", "evidence_type":"committed episode record"})
                events.append({"seq":len(events)+1, "kind":"call_finished", "actor":"judge", "text":"Recorded call provenance",
                    "summary":provenance, "turn":t["turn"], "episode_started_at":row.get("started_at"),
                    "source":f"{path}:{line}", "audit_sources":audit_sources.get(key,[]) if audited else [],
                    "evidence_type":"retroactive committed audit" if audited else "committed CLI summary",
                    "raw_available":bool(t.get("raw_trace") and ((common.REPO/"experiments/v3_instruction_compliance" if group.startswith("V3") else common.REPO)/t["raw_trace"]).is_file())})
                if t["turn"] == 1 and (row.get("tool") or {}).get("executed"):
                    events.append({"seq":len(events)+1,"kind":"tool", "actor":"judge", "text":common.canonical(row["tool"]),
                                   "source":f"{path}:{line}", "evidence_type":"committed tool record; between protocol turns 1 and 2"})
            contaminated = any(e.get("summary",{}).get("server_tool_uses") for e in events)
            models = sorted({m for e in events for m in e.get("summary",{}).get("models_used",[])})
            runs.append({"id":rid, "historical":True, "group":group, "episode_id":row["episode_id"], "source":path,
                "source_sha256":common.file_hash(common.REPO/path), "condition":row.get("condition",row.get("cell")),
                "created_at":row.get("started_at"), "model":row.get("model_requested"), "models":models,
                "status":"void development stage" if "development" in group else "historical",
                "grade":row.get("grade"), "events":events, "model_calls":len(row["turns"]),
                "note":"Original grading preserved. This is not a V4 security evaluation.",
                "advisor_active":contaminated,"void_stage":"development" in group})
    clean = sum(s.get("models_used") == ["claude-opus-5"] and not s.get("server_tool_uses") and
                not any(t != "message" for t in s.get("iteration_types",[])) for s in scored_calls)
    return {"runs":runs, "audit":{
        "unique_development_calls":len(unique_dev),
        "advisor_active_calls":sum(bool(x["server_tool_uses"]) for x in unique_dev.values()),
        "second_model_calls":sum("claude-fable-5-1" in x["models_used"] for x in unique_dev.values()),
        "clean_scored_calls":clean, "scored_calls":len(scored_calls),
        "note":"Stage 2 carries over calls from stage 1. Counts deduplicate by episode ID and turn. Raw traces were not published; the advisor attribution comes from the preserved retroactive audits.",
        "sources":["results/v2/dev_stage1/advisor_audit.json","results/v2/dev_stage2/advisor_audit.json","results/v2/episodes_scored.jsonl"]}}


def index():
    return [{k:v for k,v in row.items() if k != "events"} for row in archive()["runs"]]


def get(rid):
    return next((r for r in archive()["runs"] if r["id"] == rid), None)
