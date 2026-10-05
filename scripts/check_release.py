#!/usr/bin/env python3
"""Validate source checksums and reject accidental private/generated artifacts."""
import hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks=[]
for line in (ROOT/"SHA256SUMS").read_text().splitlines():
    digest,name=line.split("  ",1)
    path=ROOT/name
    assert path.is_file() and path.resolve().is_relative_to(ROOT),name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    checks.append(name)
if (ROOT/".git").exists():
    proc=subprocess.run(["git","ls-files","-z"],cwd=ROOT,capture_output=True,check=True)
    names=set(proc.stdout.decode().split("\0"))-{""}
    assert names==set(checks)|{"SHA256SUMS"},"Tracked files differ from source manifest"
for name in checks:
    path=ROOT/name
    assert not any(part in (".venv","__pycache__","build","results","data") for part in path.relative_to(ROOT).parts),name
    assert path.suffix not in (".pyc",".log",".lp",".deb",".o",".zip",".gz"),name
    text=path.read_text(encoding="utf-8")
    assert not re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",text),name
    assert ("/home/"+"lab/projects/") not in text and ("/mnt/d/"+"exp/") not in text,name
print(json.dumps(dict(passed=True,source_files=len(checks)+1)))
