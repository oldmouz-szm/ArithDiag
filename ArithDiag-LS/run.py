#!/usr/bin/env python3
"""Prepare, run or resume an ArithDiag-LS batch."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from arithdiag.runner import main

if __name__ == "__main__":
    raise SystemExit(main(default_backend="ArithDiag-LS"))
