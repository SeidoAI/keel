---
name: pm-plan
description: Preview what the next project scaffold would produce, with interpretation.
argument-hint: "[optional: --name project-name] [optional scope description]"
---

You are the project manager. Load the project-manager skill from
`.claude/skills/project-manager/SKILL.md` if not already active.

1. Run `keel plan --format=json` (add any name/prefix flags from $ARGUMENTS).
2. Parse the output and summarize for the user:
   - Files that would be created (with sizes and types)
   - Directory structure and its purpose
   - Which files are Jinja-rendered (customized per-project) vs verbatim copies
   - Whether the planned structure aligns with the project's conventions
3. Recommend adjustments before proceeding to `keel init`.
