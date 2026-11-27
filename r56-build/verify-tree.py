#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
import sys

root = Path(sys.argv[1]).resolve()
files = sorted(
    p for p in root.rglob("*")
    if p.is_file() and ".git" not in p.relative_to(root).parts
)
h = sha256()
for p in files:
    rel = p.relative_to(root).as_posix()
    h.update(rel.encode("utf-8") + b"\0" + sha256(p.read_bytes()).digest() + b"\n")
actual = h.hexdigest()
expected_count = 827
expected_hash = "29bd33771f52538d918b8f9c2a66e6822b84d3e2c65a9817aff926dcde5fbec5"
print(f"R56 organized source: files={len(files)} tree_sha256={actual}")
if len(files) != expected_count or actual != expected_hash:
    raise SystemExit("R56 source tree does not match the verified snapshot")
