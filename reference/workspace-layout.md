# Workspace Layout

ConvFusion's research root is **the directory Claude Code is running in** (the project directory
the user opened). There is no separate "session workspace vs. research root" split — pick the
simple, single-tier layout: everything below lives directly under the current working directory.

```text
<project root>/
├── project.md              # Research Definition — what the research is (core, at root)
├── research-state.md        # current research state + maturity (core, at root)
├── attachments/             # optional — raw input materials, never silently modified
│   ├── papers/
│   ├── datasets/
│   ├── figures/
│   └── reference/
├── plans/                   # core — plans for THIS research
│   └── history/<id>/v<NNN>.md
├── experiments/              # optional — created on demand per experiment
│   └── <name>/{data,src,scripts,results,figures}/
├── research/                 # core — structured research assets
│   ├── evidence/E<NNN>.md
│   │   └── .history/E<NNN>.<timestamp>.md
│   ├── claims/C<NNN>.md
│   ├── decisions/D<NNN>.md
│   ├── state-history/v<N>.md
│   ├── state-proposals/S<NNN>.json
│   │   └── applied.json
│   └── topic-history.json
├── papers/                   # optional — created once a paper exists
│   └── <paperId>/{paper.md, history/, latex/, figures/}
└── outputs/                   # optional — non-paper outputs
    ├── patents/
    ├── reports/
    └── slides/
```

## Rules

1. **Directories are created on demand.** Never pre-create `experiments/`, `attachments/`,
   `papers/`, or `outputs/` just because the workspace was initialized — an empty directory implies
   "you should put something here," which is misleading before there's anything to put there. Only
   `plans/` and `research/{evidence,claims,decisions,state-history}` count as **core** and should
   exist once a project is underway (create them the first time something needs to be written into
   them, not eagerly).
2. **`project.md` and `research-state.md` are the only content files at the root.** Everything else
   structured lives under `plans/`, `research/`, `papers/`, `outputs/`.
3. **Never invent a stage/step-numbered layout.** Plan ids, experiment names, etc. are named by
   capability/topic, never `step1`/`module3`-style sequence numbers (see `plans.md`).
4. A directory not in this list (e.g. a user's own `src/`, `data/`, `.git/`, `README.md`) is none of
   ConvFusion's business — never move, rename, or "clean up" anything not listed above.

## Bootstrapping a fresh workspace

The `/research` skill (see `../skills/research/SKILL.md`) is responsible for creating `project.md`
the first time a topic is given in a directory that doesn't already have one. Do not create
`research-state.md` until there's at least one real dimension to write into it (problem statement,
first piece of literature, etc.) — an empty `research-state.md` with no dimensions is not useful and
should not be pre-created either.

## Is this a research workspace?

A directory counts as an active ConvFusion research workspace if either `project.md` or
`research-state.md` exists at its root. If neither exists, treat `/research <topic>` as the trigger
to bootstrap a new one there.
