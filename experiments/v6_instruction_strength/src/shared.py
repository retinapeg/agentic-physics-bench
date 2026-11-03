"""Explicit imports of the preserved V5 implementation; no process-global patches."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V5 = ROOT / 'experiments/v5_tool_difficulty/src'

def load(name):
    spec = importlib.util.spec_from_file_location('_v6_shared_' + name, V5 / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

engine = load('engine')
analysis = load('analyze')
tasks = load('tasks')
adapter = load('adapter')


def load_local(name):
    spec = importlib.util.spec_from_file_location('_v6_local_' + name, Path(__file__).parent / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
