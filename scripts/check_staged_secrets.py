#!/usr/bin/env python3
"""Conservative pre-publish guard; not a substitute for reviewing staged files."""
import re
import subprocess
import sys
from pathlib import PurePosixPath

patterns = [
    re.compile(rb"(?:gh" + rb"p_|github_" + rb"pat_)[A-Za-z0-9_]{20,}"),
    re.compile(rb"sk-" + rb"(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}"),
    re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
]

names = subprocess.check_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]).split(b"\0")
errors = []
for raw in filter(None, names):
    name = raw.decode("utf-8")
    path = PurePosixPath(name)
    if ((path.name.startswith(".env") and path.name != ".env.example")
        or any(p in {"secrets", "exports", ".venv", "data"} for p in path.parts)
        or path.suffix.lower() in {".fit", ".gpx", ".tcx", ".sqlite", ".db"}
        or path.name in {"api-key", "http-token"}):
        errors.append(name)
        continue
    body = subprocess.check_output(["git", "show", ":" + name])
    if any(p.search(body) for p in patterns):
        errors.append(name)
if errors:
    print("Publication blocked: review these files for secrets/private data:", file=sys.stderr)
    for name in errors:
        print(" - " + name, file=sys.stderr)
    sys.exit(1)
print("Staged-file guard passed. Still review your diff before publishing.")
