"""Explicit namespaced reuse of the frozen native adapter and numerical helpers."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('_apb_v10_v8_helpers',ROOT/'experiments/v8_revocation/src/run_v8.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
