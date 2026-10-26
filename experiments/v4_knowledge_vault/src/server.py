"""Loopback-only V4 dashboard. Python standard library; no remote hosting or dependencies."""
import argparse
import json
import mimetypes
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import common
import history
import baseline
from adapter import MODELS, preflight
from engine import Run, verify_events, validate_config
from judge import aggregate
from scenarios import CATALOG


def saved_runs():
    rows = []
    directories={directory.name:directory for collection in ("examples","runs") for directory in (common.RESULTS/collection).glob("v4-*")}
    for directory in directories.values():
        try:
            if (directory / "run.json").exists():
                row = json.loads((directory / "run.json").read_text())
                events = [json.loads(s) for s in (directory / "events.jsonl").read_text().splitlines()]
                manifest = json.loads((directory / "manifest.json").read_text())
                row["integrity_verified"] = (verify_events(events) and row["events"] == events and
                    row["manifest_sha256"] == common.digest(manifest))
            else:
                m = json.loads((directory / "manifest.json").read_text())
                events = []
                for line in (directory / "events.jsonl").read_text().splitlines():
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        break
                row = {"id":directory.name,"status":"interrupted","config":m["config"],"challenge":m["public_task"],
                       "created_at":m["created_at"],"events":events,"verdict":None,"metrics":{},
                       "integrity_verified":False,"limits":m["limits"],"provenance":m["identity"]}
            rows.append(row)
        except (ValueError, OSError, KeyError):
            rows.append({"id":directory.name,"status":"unreadable evidence","integrity_verified":False,"events":[]})
    return sorted(rows,key=lambda row:row.get("created_at",""),reverse=True)


class Lab:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.identity = preflight()
        self.lock = threading.Lock()
        self.current = None

    def launch(self, config):
        with self.lock:
            if self.current and self.current.state["status"] in ("ready", "running"):
                raise ValueError("A run is already active; stop it before launching another")
            config = validate_config(config)
            if config["split"] != "dev":
                raise ValueError("The dashboard launches development runs only")
            if not self.identity.get("ready"):
                raise ValueError(self.identity.get("reason", "CLI preflight failed"))
            self.current = Run(config,self.identity)
            threading.Thread(target=self.current.execute, daemon=True).start()
            return self.current.snapshot()


def handler_for(lab):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, payload, mime="application/json"):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if mime == "application/json" else payload
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def local_request(self):
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in expected

        def do_GET(self):
            if not self.local_request():
                return self.respond(403, {"error":"Loopback host required"})
            path = urlsplit(self.path).path
            if path == "/api/bootstrap":
                return self.respond(200, {"csrf":lab.token,"catalog":CATALOG,"models":MODELS,
                    "preflight":{k:v for k,v in lab.identity.items() if k != "binary"},
                    "history":history.index(),"audit":history.archive()["audit"]})
            if path == "/api/runs":
                runs = saved_runs()
                if lab.current:
                    runs = [lab.current.snapshot()] + [r for r in runs if r["id"] != lab.current.id]
                return self.respond(200, [{k:v for k,v in r.items() if k != "events"} for r in runs])
            if path == "/api/compare":
                return self.respond(200, aggregate([r for r in saved_runs() if r.get("config") and r.get("integrity_verified")]))
            match = re.fullmatch(r"/api/runs/((?:v4|history)-[a-f0-9]{16})", path)
            if match:
                rid = match[1]
                row = (lab.current.snapshot() if lab.current and rid == lab.current.id else
                       history.get(rid) if rid.startswith("history-") else next((r for r in saved_runs() if r["id"]==rid), None))
                return self.respond(200 if row else 404, row or {"error":"Run not found"})
            files = {"/":"index.html", "/app.js":"app.js", "/style.css":"style.css"}
            if path in files:
                file = common.ROOT/"web"/files[path]
                return self.respond(200,file.read_bytes(),mimetypes.guess_type(str(file))[0]+"; charset=utf-8")
            self.respond(404, {"error":"Not found"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            if not self.local_request() or origin not in (None, "http://"+self.headers.get("Host", "")) or self.headers.get("X-Vault-CSRF") != lab.token:
                return self.respond(403,{"error":"Local same-origin request and session token required"})
            if self.headers.get("Content-Type") != "application/json":
                return self.respond(415,{"error":"JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32768:
                    raise ValueError("Request size out of bounds")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError("JSON object required")
                if self.path == "/api/runs":
                    if data.get("opt_in") is not True:
                        raise ValueError("Explicit inference opt-in is required for each run")
                    return self.respond(201,lab.launch(data.get("config",{})))
                if self.path == "/api/baseline":
                    with lab.lock:
                        if lab.current and lab.current.state["status"] in ("ready","running"):
                            raise ValueError("Wait for or stop the active model run before recording a baseline")
                        result=baseline.execute(data.get("config",{}))
                    return self.respond(201,result)
                if self.path == "/api/stop":
                    with lab.lock:
                        if lab.current:
                            lab.current.cancelled.set()
                    return self.respond(200,{"stopping":True})
                self.respond(404,{"error":"Not found"})
            except (ValueError, TypeError, KeyError) as exc:
                self.respond(400,{"error":str(exc)})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8741)
    args=parser.parse_args()
    lab=Lab()
    server=ThreadingHTTPServer(("127.0.0.1",args.port),handler_for(lab))
    print(f"Knowledge Vault: http://127.0.0.1:{args.port} (inference off until explicitly enabled)",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if lab.current:
            lab.current.cancelled.set()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
