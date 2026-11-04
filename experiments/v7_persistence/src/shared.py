"""Read-only imports of frozen V5 numeric task and validation helpers."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
def v5(name):
    spec=importlib.util.spec_from_file_location('_v7_v5_'+name,ROOT/'experiments/v5_tool_difficulty/src'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
engine=v5('engine')
tasks=v5('tasks')
