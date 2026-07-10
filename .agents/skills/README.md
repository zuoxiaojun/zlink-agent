# Project-level skills (placeholder)

This directory is reserved for **project-local** Codex/ECC skills that should
ship with the ZLink Agent repository.

## Current state

Empty. All active skills today come from the user-level pool at
`~/.codex/.agents/skills/` (see the home-directory listing).

## When to add a skill here

Add a project-local skill when **all** of the following hold:

1. The skill encodes ZLink Agent-specific knowledge (e.g. ERP data model,
   YonSuite SDK gotchas, build-script quirks) that is not useful outside
   this repo.
2. You want every contributor to load it automatically — no per-user install.
3. You do NOT want the skill to drift across projects (use the user-level
   pool instead).

## Format

Each skill is a subdirectory containing at minimum a `SKILL.md`:

```
.agents/skills/<skill-name>/
├── SKILL.md          # required — frontmatter + instructions
├── agents/openai.yaml # required — Codex interface metadata
├── references/        # optional — large docs loaded on demand
└── scripts/           # optional — runnable helpers
```

See `~/.codex/.agents/skills/tdd-workflow/` for a concrete example.
