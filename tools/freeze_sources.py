#!/usr/bin/env python3
"""Create a source-only integrity manifest after a reviewed source change."""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
INCLUDED = {".py", ".cpp", ".h", ".md", ".yml", ".yaml", ".txt", ".toml"}
NAMES = {"Makefile", "LICENSE", ".gitignore", ".gitattributes"}
DIRECTORIES = {
    "src",
    "ArithDiag-G",
    "ArithDiag-LS",
    "tests",
    "tools",
    "docs",
    ".github",
}
paths = []
for path in ROOT.rglob("*"):
    relative = path.relative_to(ROOT)
    if len(relative.parts) > 1 and relative.parts[0] not in DIRECTORIES:
        continue
    if not path.is_file() or any(
        part.startswith(".") and part != ".github"
        for part in path.relative_to(ROOT).parts[:-1]
    ):
        continue
    if any(
        part in {"build", "__pycache__", "results"}
        for part in path.relative_to(ROOT).parts
    ):
        continue
    if path.suffix in INCLUDED or path.name in NAMES:
        paths.append(path)
version_tree = ast.parse((ROOT / "src/arithdiag/__init__.py").read_text(encoding="utf-8"))
version = next(
    ast.literal_eval(node.value)
    for node in version_tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
)
manifest = dict(
    schema="arithdiag-source-v1",
    version=version,
    files={
        str(p.relative_to(ROOT))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in sorted(paths)
    },
)
(ROOT / "SOURCE_MANIFEST.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(json.dumps(dict(source_files=len(paths), manifest="SOURCE_MANIFEST.json")))
