#!/usr/bin/env python3
"""fake-gh — stand-in for `gh` CLI in unit tests.

Records every invocation to $FAKE_GH_LOG, plus:
- ``pr create ... --repo R --head B ...`` emits a fake URL to stdout.
- ``pr list --repo R --head B --json url`` emits [] or [{"url": ...}]
  based on $FAKE_GH_EXISTING_PRS.
- ``pr edit ...`` succeeds silently.
- ``pr merge ...`` succeeds silently.
"""

import os
import sys


def main() -> int:
    log = os.environ.get("FAKE_GH_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(" ".join(sys.argv[1:]) + "\n")

    args = sys.argv[1:]
    if not args:
        return 0

    if args[:2] == ["pr", "create"]:
        repo = _flag(args, "--repo", default="unknown/repo")
        branch = _flag(args, "--head", default="unknown")
        sys.stdout.write(
            f"https://github.com/{repo}/pull/{abs(hash((repo, branch))) % 1000}\n"
        )
        return 0
    if args[:2] == ["pr", "list"]:
        existing = os.environ.get("FAKE_GH_EXISTING_PRS", "[]")
        sys.stdout.write(existing)
        return 0
    if args[:2] == ["pr", "edit"]:
        return 0
    if args[:2] == ["pr", "merge"]:
        return 0
    return 0


def _flag(args: list[str], name: str, default: str = "") -> str:
    if name in args:
        return args[args.index(name) + 1]
    return default


if __name__ == "__main__":
    sys.exit(main())
