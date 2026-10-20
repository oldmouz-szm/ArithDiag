"""Shared input paths and semantic validation; no backend encoding."""
import os
from pathlib import Path
from arithdiag import model as builder
from arithdiag.validation import validate

ROOT = Path(__file__).resolve().parents[2]
IQ = Path(os.environ.get("ARITHDIAG_DATASET_ROOT", str(ROOT / "data/benchmark"))).expanduser().resolve()

def load_builder():
    return builder

def validation_failure(check):
    return "original_model_validation_failed; violation_count=" + str(len(check.get("errors", ())))
