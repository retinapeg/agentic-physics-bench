"""Local V4 commands. Inference always requires --opt-in."""
import argparse
import json
from pathlib import Path

import common
from adapter import preflight
from engine import Run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    baseline = sub.add_parser("baseline",help="Record the non-LLM gate executing fixed probes; zero inference")
    baseline.add_argument("--family",default="exact_secret")
    baseline.add_argument("--turns",type=int,default=2)
    frozen = sub.add_parser("freeze", help="Create a new prospective paired V4 held-out plan; no inference")
    frozen.add_argument("--config", type=Path, required=True)
    frozen.add_argument("--cases", type=int, default=10)
    heldout = sub.add_parser("heldout-next", help="Attempt exactly one previously unattempted frozen V4 episode")
    heldout.add_argument("campaign", type=Path)
    heldout.add_argument("--opt-in", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--opt-in", action="store_true")
    run.add_argument("--turns", type=int, default=1)
    run.add_argument("--budget", type=float, default=.4)
    run.add_argument("--family", default="exact_secret")
    run.add_argument("--model", default="claude-fable-5-1")
    run.add_argument("--defence", choices=["prompt_only", "enforced"], default="prompt_only")
    args = parser.parse_args()
    if args.command == "preflight":
        print(json.dumps(preflight(), indent=2))
    elif args.command == "baseline":
        import baseline
        result=baseline.execute({"family":args.family,"turn_budget":args.turns})
        print(json.dumps({"id":result["id"],"verdict":result["verdict"],"metrics":result["metrics"]},indent=2))
    elif args.command == "freeze":
        from campaign import freeze
        folder,manifest=freeze(json.loads(args.config.read_text()),args.cases)
        print(json.dumps({"directory":str(folder),"manifest_sha256":common.digest(manifest),"planned_calls":manifest["planned_calls"],"planned_cli_budget_usd":manifest["planned_cli_budget_usd"]},indent=2))
    elif args.command == "heldout-next":
        from campaign import run_next
        result=run_next(args.campaign,args.opt_in)
        print(json.dumps({"id":result["id"],"status":result["status"],"verdict":result["verdict"]},indent=2))
    elif args.command == "run":
        if not args.opt_in:
            parser.error("Inference is off. --opt-in is required.")
        identity = preflight()
        if not identity["ready"]:
            parser.error(identity.get("reason", "CLI preflight failed"))
        job = Run({"turn_budget": args.turns, "max_cost_usd": args.budget, "family": args.family, "defence": args.defence,
                   "attacker_model": args.model, "defender_model": args.model}, identity)
        print("Run:", job.id, flush=True)
        result = job.execute()
        print(json.dumps({"id":result["id"], "status":result["status"], "verdict":result["verdict"], "metrics":result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
