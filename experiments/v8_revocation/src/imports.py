"""Explicit namespaced imports; never mutate V7 or process-global import paths."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
transport=load('_apb_v8_native_adapter','experiments/v7_persistence/src/adapter.py')
engine=load('_apb_v8_numeric_engine','experiments/v5_tool_difficulty/src/engine.py')
tasks=load('_apb_v8_tasks','experiments/v5_tool_difficulty/src/tasks.py')
