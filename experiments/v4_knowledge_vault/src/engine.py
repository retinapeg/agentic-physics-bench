"""Bounded state machine. Every visible event has an append-only execution record."""
import json
import math
import os
import threading
import uuid

import common
from adapter import MODELS, ClaudeAdapter
from scenarios import CATALOG, generate, defender_system, attacker_system, release_gate, permitted_observation
from judge import judge

LOADED_SOURCE_HASHES = common.frozen_code()


class IncompleteConversation(RuntimeError):
    """A recorded task-format outcome, distinct from a provenance-control failure."""


def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError("Configuration must be an object")
    defaults = {"family": "exact_secret", "difficulty": "standard", "defence": "prompt_only",
                "attacker_model": MODELS[0], "defender_model": MODELS[0], "turn_budget": 2,
                "max_cost_usd": .6, "timeout_s": 180, "split": "dev"}
    if set(value) - set(defaults):
        raise ValueError("Unknown configuration fields")
    c = {**defaults, **value}
    if c["family"] not in CATALOG or c["difficulty"] not in ("standard", "hard"):
        raise ValueError("Invalid challenge")
    if c["defence"] not in ("prompt_only", "enforced") or c["split"] not in ("dev", "heldout"):
        raise ValueError("Invalid policy or split")
    if any(c[k] not in MODELS for k in ("attacker_model", "defender_model")):
        raise ValueError("Choose an explicit supported model identity")
    if type(c["turn_budget"]) is not int or not 1 <= c["turn_budget"] <= 6:
        raise ValueError("Turn budget must be an integer from 1 to 6")
    for k, low, high in (("max_cost_usd", .04, 2), ("timeout_s", 5, 180)):
        if type(c[k]) not in (int, float) or not math.isfinite(c[k]) or not low <= c[k] <= high:
            raise ValueError(f"{k} must be between {low} and {high}")
    return c


def verify_events(events):
    previous = "0" * 64
    for i, event in enumerate(events):
        payload = {k: v for k, v in event.items() if k != "hash"}
        if event.get("seq") != i + 1 or event.get("previous_hash") != previous or common.digest(payload) != event.get("hash"):
            return False
        previous = event["hash"]
    return True


def record_event(directory, state, kind, actor, text, **extra):
    """Shared append-only evidence writer for live agents and the deterministic baseline."""
    events = state["events"]
    event = {"seq": len(events)+1, "time": common.now(), "kind": kind, "actor": actor, "text": text,
             "previous_hash": events[-1]["hash"] if events else "0"*64, **extra}
    event["hash"] = common.digest(event)
    with (directory / "events.jsonl").open("a") as out:
        out.write(common.canonical(event) + "\n")
        out.flush()
        os.fsync(out.fileno())
    events.append(event)
    return event["seq"]


class Run:
    def __init__(self, config, identity, adapter=None, results=None, seeds=None, campaign=None):
        if common.frozen_code() != LOADED_SOURCE_HASHES:
            raise ValueError("Source changed after Python loaded it. Restart the server before launching a run.")
        self.config = validate_config(config)
        if self.config["split"] == "heldout" and not campaign:
            raise ValueError("Held-out execution requires a verified campaign freeze")
        self.id = "v4-" + uuid.uuid4().hex[:16]
        self.results = results or common.RESULTS
        self.cancelled = threading.Event()
        self.lock = threading.RLock()
        self.adapter = adapter or ClaudeAdapter(identity)
        self.public, self.oracle = generate(self.config["family"], self.config["difficulty"], **(seeds or {}))
        self.identity = identity
        self.code_hashes = common.frozen_code()
        self.max_calls = 2 * self.config["turn_budget"] + 2
        self.exchanges = []
        self.guesses = []
        self.transcript = []  # This is the only conversation passed to the attacker.
        self.state = {"id": self.id, "created_at": common.now(), "status": "ready", "config": self.config,
            "challenge": self.public, "events": [], "verdict": None,
            "metrics": {"inference_calls": 0, "reported_model_turns":0, "input_tokens":0, "output_tokens":0,
                        "turns": 0, "observed_cost_usd": 0, "unknown_cost_calls": 0},
            "limits": {"max_calls": self.max_calls, "turns": self.config["turn_budget"],
                       "output_tokens_per_call": 512, "timeout_s_per_call": self.config["timeout_s"],
                       "max_model_process_seconds": self.max_calls * self.config["timeout_s"],
                       "cli_budget_usd": self.config["max_cost_usd"]},
            "provenance": {k:v for k,v in identity.items() if k != "binary"},
            "source": "real_model" if adapter is None else "injected_test_adapter"}
        manifest = {"protocol": "v4.0.0-dev", "created_at": self.state["created_at"], "config": self.config,
            "identity": self.state["provenance"], "code_sha256": self.code_hashes,
            "private_seed_commitment": common.digest(self.oracle), "public_task": self.public,
            "limits": self.state["limits"], "campaign": campaign}
        self.state["manifest_sha256"] = common.digest(manifest)
        self.directory = self.results / "runs" / self.id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.raw = self.results / "raw" / self.id
        common.write_new(self.raw / "private.json", self.oracle, private=True)
        common.write_new(self.directory / "manifest.json", manifest)
        self.emit("freeze", "judge", "Run configuration frozen before inference", manifest_sha256=self.state["manifest_sha256"],
                  private_seed_commitment=manifest["private_seed_commitment"], audience="operator")

    def emit(self, kind, actor, text, **extra):
        with self.lock:
            return record_event(self.directory,self.state,kind,actor,text,**extra)

    def snapshot(self):
        with self.lock:
            return json.loads(common.canonical(self.state))

    def call(self, role, system, prompt):
        m = self.state["metrics"]
        if self.cancelled.is_set():
            raise RuntimeError("Stopped by operator")
        if common.frozen_code() != self.code_hashes:
            raise RuntimeError("Source or protocol changed after run freeze")
        if m["inference_calls"] >= self.max_calls or m["observed_cost_usd"] >= self.config["max_cost_usd"]:
            raise RuntimeError("Run budget exhausted")
        m["inference_calls"] += 1
        m["unknown_cost_calls"] += 1
        index = m["inference_calls"]
        # Fixed equal allocation means no extra call can borrow a later call's allowance.
        allowance = self.config["max_cost_usd"] / self.max_calls
        model = self.config[role+"_model"]
        common.write_new(self.raw / f"call-{index}-input.json", {"role": role, "system": system, "prompt": prompt}, private=True)
        self.emit("call_started", role, f"Inference {index}/{self.max_calls}", model=model, call=index,
                  system_sha256=common.digest(system), prompt_sha256=common.digest(prompt), usd_limit=allowance)
        call, summary, violations = self.adapter.call(role, model, system, prompt, allowance, self.config["timeout_s"], self.cancelled)
        common.write_new(self.raw / f"call-{index}.json", call, private=True)
        cost = (summary.get("result") or {}).get("list_price_estimate_usd")
        for source,target in (("num_turns","reported_model_turns"),("reported_input_tokens","input_tokens"),("output_tokens","output_tokens")):
            value=(summary.get("result") or {}).get(source)
            if type(value) is int and value >= 0:
                m[target]+=value
        if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
            m["unknown_cost_calls"] -= 1
            m["observed_cost_usd"] += cost
            if cost > allowance:
                violations.append("cli_budget_overshoot")
        else:
            violations.append("missing_cost_evidence")
        self.emit("call_finished", role, "Provenance accepted" if not violations else "Execution stopped: provenance or budget failure",
                  call=index, summary=summary, violations=violations, elapsed_s=call["elapsed_s"],
                  raw_sha256=common.file_hash(self.raw / f"call-{index}.json"))
        if violations:
            raise RuntimeError("; ".join(violations))
        return summary.get("result_text") or ""

    def defend(self, request, kind, turn):
        self.emit("message", "user" if kind == "legitimate" else "attacker", request, turn=turn, request_kind=kind,
                  flow="authorised" if kind == "legitimate" else "untrusted", audience="defender")
        candidate = self.call("defender", defender_system(self.public, self.oracle, self.config["defence"]),
            common.canonical({"released_history": self.transcript, "request": request, "request_kind": kind}))
        released = candidate
        if self.config["defence"] == "enforced":
            self.emit("candidate", "defender", candidate, turn=turn, audience="operator", flow="private")
            released, reason = release_gate(self.public, kind, candidate, permitted_observation(self.public,self.oracle))
            self.emit("gate", "judge", reason, turn=turn, flow="authorised" if kind == "legitimate" else "blocked")
        seq = self.emit("message", "defender", released, turn=turn, audience="attacker", flow="released", request_kind=kind)
        self.exchanges.append({"event": seq, "kind": kind, "candidate": candidate, "released": released})
        self.transcript.extend([{"role": "user", "content": request}, {"role": "defender", "content": released}])

    def execute(self):
        valid, completed = True, False
        self.state["status"] = "running"
        try:
            self.defend(self.public["task"], "legitimate", 0)
            for turn in range(1, self.config["turn_budget"]+1):
                self.state["metrics"]["turns"] = turn
                response = self.call("attacker", attacker_system(self.public),
                    common.canonical({"turn": turn, "turn_budget": self.config["turn_budget"], "released_history": self.transcript}))
                try:
                    proposal = json.loads(response)
                    if not isinstance(proposal, dict) or not isinstance(proposal.get("message"), str) or not 1 <= len(proposal["message"]) <= 6000:
                        raise ValueError()
                except (ValueError, TypeError):
                    self.emit("format_error", "attacker", response, turn=turn)
                    raise IncompleteConversation("Malformed attacker output; no repair or retry")
                seq = self.emit("attack_proposal", "attacker", response, turn=turn, audience="operator")
                self.guesses.append({"event":seq,"value":proposal.get("guess"),"seen_events":[x["event"] for x in self.exchanges]})
                self.defend(proposal["message"], "attack", turn)
            self.defend("Return to the authorised task. " + self.public["task"], "legitimate", self.config["turn_budget"]+1)
            completed = True
        except IncompleteConversation as exc:
            self.emit("error", "judge", str(exc), audience="operator", category="task_format")
        except Exception as exc:
            valid = False
            self.emit("error", "judge", str(exc), audience="operator")
        self.state["verdict"] = judge(self.public, self.oracle, self.exchanges, valid, completed, self.guesses)
        self.state["status"] = "completed" if completed else "stopped" if self.cancelled.is_set() else "invalid"
        self.emit("verdict", "judge", self.state["verdict"]["verdict"], verdict=self.state["verdict"])
        self.state["finished_at"] = common.now()
        common.write_new(self.directory / "run.json", self.state)
        return self.snapshot()
