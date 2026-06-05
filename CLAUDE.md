# Project: JangLabs

JangLabs is a **multi-lab workspace** for AI-assisted experimentation. It is a thin
coordinator: it owns almost no content of its own. Each top-level directory is an
independent project ("lab") that lives in **its own git repository** and is wired in
here as a **git submodule**.

---

## The workspace invariant (read this first)

> **Every top-level directory whose name does not begin with `.` is a nested
> repository (a git submodule) — with a single exception, `build/`. Nothing else
> may live at the workspace root.**

There are exactly four kinds of entry allowed at the root of JangLabs:

1. **Submodules** — one per lab. Each is its own repo with its own remote, history,
   `CLAUDE.md`, conventions, and lifecycle. Pinned here by commit SHA.
2. **Dot-files / dot-directories** — `.git`, `.gitmodules`, `.gitignore`,
   `.devcontainer/`, `.claude-workspace`. Tooling and config only.
3. **Root coordinator files** — `CLAUDE.md` (this file), `README.md`, `AGENTS.md`.
   These describe the workspace; they do not implement any lab.
4. **`build/`** — the single sanctioned exception: a non-submodule output directory
   where compiled binaries/artifacts from the labs' tools are collected (namespaced
   per lab, e.g. `build/jangsjyro/`). Its contents are git-ignored — only
   `build/README.md` is tracked. This is the *only* non-submodule, non-dot directory
   permitted at the root; do not add others.

**Consequences — enforce these:**

- **Never** create a plain (non-submodule) directory at the root other than `build/`.
  No `assets/`, no `shared/`, no `scratch/`, no `tmp/`. If something needs a home, it
  belongs *inside* a lab (each lab has its own `reference/`, `findings/`, `tools/`,
  etc.) — except compiled output, which goes in `build/`.
- **Never** add a loose file at the root other than the three coordinators above.
- To bring **new** work into the workspace, it must become **its own repo + submodule**
  — see *Adding a lab*. Do not "just drop it in" as a folder.
- A lab is referenced from another lab **by path** (e.g. `../<sibling-lab>`), never by
  copying/vendoring its files into the root or into another lab. (Honors the repo rule:
  no absolute-path symlinks; reference by path or URL.)

This invariant is what makes the workspace cleanly separable, independently
cloneable per lab, and free of cross-lab contamination.

---

## Structure — the labs

All four lab directories are submodules (`git submodule status` to see pinned SHAs).
**Naming:** the submodule path is lowercase; its repo is that path PascalCased with a
`JangLabs-` prefix (`agent` → `JangLabs-Agent`).

| Lab (submodule) | Repository | Branch | Focus | Entry doc |
|---|---|---|---|---|
| `agent/` | [`JangMan-J/JangLabs-Agent`](https://github.com/JangMan-J/JangLabs-Agent) | `main` | Multi-agent coordination skills — the Convergent Arbiter skill package; ACP / Agent-Teams arbiter prompts. | `agent/CLAUDE.md` |
| `claude/` | [`JangMan-J/JangLabs-Claude`](https://github.com/JangMan-J/JangLabs-Claude) | `main` | The Claude Code harness for this box — hooks, `CLAUDE.md` fragment, settings; installed globally via `agent-harness.py`. | `claude/CLAUDE.md` |
| `jangsjyro/` | [`JangMan-J/JangLabs-JangsJyro`](https://github.com/JangMan-J/JangLabs-JangsJyro) | `branch-a-port` | The JangsJyro JoyShockMapper fork (C++23, upstream-facing). Also hosts the `gamepad/` input-research lab (8BitDo Ultimate 2 / gyro / Steam-Input-vs-JSM) as a subdir. | `jangsjyro/AGENTS.md` |
| `proton/` | [`JangMan-J/JangLabs-Proton`](https://github.com/JangMan-J/JangLabs-Proton) | `main` | ProtonDB-driven Linux/Proton config inference (the `protondb-tuner` skill). | `proton/CLAUDE.md` |

`jangsjyro` is the structural model the others now follow: an independent repo, pinned
by SHA, never vendored into JangLabs history (it was the one lab already independent
before the others were extracted). The three others (`JangLabs-Agent`/`JangLabs-Claude`/
`JangLabs-Proton`) were fresh-init extractions of
formerly in-tree labs (their pre-extraction history lives in JangLabs' own git log). All
four repos now share the `JangLabs-` name prefix (its repo is `JangLabs-JangsJyro`). (A
sixth, `JangLabs-Gamepad`, was likewise extracted but has since been folded into
`jangsjyro/gamepad/` and its submodule retired — its history remains in JangLabs' git log.
`JangLabs-Theme` was similarly extracted, then removed as a submodule on 2026-06-04 — its
repo remains on GitHub and its in-tree history lives in JangLabs' git log.)

---

## Working in this repo

**Start at the lab boundary, not the repo root.** A task is almost always *inside one
lab*. The moment your work concerns a lab, that lab's own `CLAUDE.md` (or entry doc) is
the authority — see *Lab scoping*.

### Submodule mechanics

- **Clone:** `git clone --recurse-submodules https://github.com/JangMan-J/JangLabs.git`. On an existing checkout
  that is missing lab contents: `git submodule update --init --recursive`.
- **A lab is pinned by SHA.** JangLabs records *which commit* of each lab it expects.
  After you commit inside a lab, JangLabs shows the submodule as modified until you
  bump the pointer.
- **Editing a lab:** `cd <lab>/`, make changes, **commit and push inside the lab**
  (the lab is its own repo — that is where its history lives), then back at the root
  `git add <lab> && git commit` to **bump the pinned SHA**. Never try to commit a
  lab's file changes from the JangLabs index — they live in the submodule.
- **Pull a lab's latest:** `git submodule update --remote <lab>` advances it to the tip
  of its tracked branch (`main`, or `branch-a-port` for `jangsjyro`); then bump the
  pointer as above.
### Adding a lab

1. Create the lab as its **own** git repo (submodule `foo` → repo `JangLabs-Foo`),
   push it to a remote.
2. `git submodule add -b <branch> <url> <name>` at the JangLabs root (path stays lowercase).
3. `git commit`. Add a row to the table above and to `README.md`.

Do **not** add a lab by creating a plain directory — that violates the invariant and
breaks the scoping tooling.

---

## Lab scoping — the context re-scoping mechanism

Context narrows to the lab you are working in. This is delivered two ways, a convention
and an automation, so re-scoping is intuitive as you move between subdirectories.

### The protocol (convention)

- **The active scope is your working subdirectory.** At the JangLabs root, this file is
  the authority. The moment your cwd (or your edits) enter `<lab>/`, that lab's entry
  doc becomes the authority and **overrides this root** for everything inside the lab.
- **On entering a lab, read its entry doc first** (precedence:
  `CLAUDE.md` → `AGENTS.md` → `README.md` → `HANDOFF.md`). Every lab `CLAUDE.md` opens
  with a "Lab scope" banner restating this.
- **Don't cross lab boundaries.** Conventions in one lab (e.g. `jangsjyro/`'s upstream-facing-diff
  discipline) do not apply to another (e.g. `agent/`'s skill-prompt contract). Don't
  edit or import a sibling lab from inside one — reference it by path/URL if needed.
- **Resumable handoffs are sacred.** Where a lab has `handoffs/` or a `HANDOFF.md`, each
  is meant to let a fresh session pick up cold. Don't edit them casually.
- **Findings are append-only knowledge.** `findings/*.md` records non-obvious facts
  learned across sessions; add to them when a discovery would otherwise be lost.

### The automation (`lab-scope` hook)

The `claude/` harness ships `hooks/lab-scope.sh` (a `UserPromptSubmit` hook). It walks
up from the session's working directory to the `.claude-workspace` marker at the
workspace root; when found, it treats each top-level non-dot child (except `build/`) as a
lab and, **the moment the active lab changes**, injects a one-paragraph scope banner naming the lab and
its entry doc. It is silent off-workspace and when the lab is unchanged, so it costs
nothing until you actually re-scope.

- **Enable it:** from `claude/`, run `./agent-harness.py install --apply`, then restart
  Claude Code (or `/reload-plugins`). It registers alongside the other harness hooks.
- **The marker** (`.claude-workspace`) is what flags this tree as a multi-lab workspace.
  Keep it at the root. The mechanism is generic — any future workspace that drops the
  same marker gets the same scoping behavior.

---

## Repo-level conventions

- **Branch for PRs:** `main` (in JangLabs and in each lab repo).
- **No build *system* at the workspace root** — each lab owns its own build/deps
  (usually ad-hoc Python; some have their own `requirements.txt`). Compiled *output*,
  however, is collected at the root in **`build/`** (the one sanctioned non-submodule
  dir; contents git-ignored, namespaced per lab — see `build/README.md`).
- **Avoid absolute-path symlinks** — they break on clone. Reference other work by path
  (within a checkout) or by URL; never vendor a sibling lab's files.
- **Large binary artifacts** (screenshots, HID dumps, capture logs) live under the
  owning lab's `reference/` or `runs/`, never at the workspace root.
- **`.devcontainer/`** provides a reproducible container (Python 3.12 + uv + ruff +
  shellcheck + Node LTS); it is a dot-dir and is exempt from the lab rule.
