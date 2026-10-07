"""Gate for confirmatory study 2: run before any instance of the study is solved.

Passes only if
  1. FROZEN_MANIFEST_2.json exists and every listed file matches it;
  2. the protocol and the manifest are committed in HEAD, unchanged;
  3. HEAD is pushed to origin/main;
  4. a tag on origin whose name starts with "protocol-2" points at HEAD
     (the release that Zenodo archives);
  5. results/confirm2 does not exist yet (nothing has been run).

Usage (from the package root): python code/check_freeze_2.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "code")
from confirm_analysis_hgs import MANIFEST_FILES  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main():
    problems = []
    man_path = Path("FROZEN_MANIFEST_2.json")
    if not man_path.exists():
        problems.append("FROZEN_MANIFEST_2.json is missing: run code/freeze_manifest_hgs.py, then commit and push")
    else:
        man = json.loads(man_path.read_text())
        for rel in MANIFEST_FILES:
            if man.get(rel) != hashlib.sha256(Path(rel).read_bytes()).hexdigest():
                problems.append(f"{rel} differs from FROZEN_MANIFEST_2.json")
        for rel in ("FROZEN_MANIFEST_2.json", "CONFIRMATORY_PROTOCOL_2.md"):
            committed = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True).stdout
            if committed != Path(rel).read_bytes():
                problems.append(f"{rel} is not committed in HEAD as it stands")
    head = git("rev-parse", "HEAD")
    remote_main = git("ls-remote", "origin", "refs/heads/main").split("\t")[0]
    if remote_main != head:
        problems.append(f"HEAD {head[:8]} is not pushed to origin/main ({remote_main[:8] or 'unreachable'})")
    tags = {}
    for line in git("ls-remote", "--tags", "origin").splitlines():
        sha, ref = line.split("\t")
        name = ref.removeprefix("refs/tags/").removesuffix("^{}")
        if ref.endswith("^{}") or name not in tags:
            tags[name] = sha
    if not any(n.startswith("protocol-2") and sha == head for n, sha in tags.items()):
        problems.append("no tag on origin starting with 'protocol-2' points at HEAD: publish the GitHub release")
    if Path("results/confirm2").exists():
        problems.append("results/confirm2 already exists: move it aside (see NEXT_RUNS_2.md) before starting")
    if problems:
        print("FREEZE NOT VERIFIED - do not run the study:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"FREEZE VERIFIED at {head}. The study may be run.")


if __name__ == "__main__":
    main()
