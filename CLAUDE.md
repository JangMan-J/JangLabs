# Project: JangLabs

JangLabs is a **multi-lab workspace** for AI-assisted experimentation. It is a thin
coordinator: it owns almost no content of its own. Each top-level directory is an
independent project ("lab") that lives in **its own git repository** and is wired in
here as a **git submodule**.

---

## The workspace invariant (read this first)

> **Every top-level directory whose name does not begin with `.` is a nested
> repository (a git submodule). Nothing else may live at the workspace root.**

There are exactly three kinds of entry allowed at the root of JangLabs:

1. **Submodules** — one per lab. Each is its own repo with its own remote, history,
   `CLAUDE.md`, conventions, and lifecycle. Pinned here by commit SHA.
2. **Dot-files / dot-directories** — `.git`, `.gitmodules`, `.gitignore`,
   `.devcontainer/`, `.claude-workspace`. Tooling and config only.
3. **Root coordinator files** — `CLAUDE.md` (this file), `README.md`, `AGENTS.md`.
   These describe the workspace; they do not implement any lab.

**Consequences — enforce these:**

- **Never** create a plain (non-submodule) directory at the root. No `assets/`, no
  `shared/`, no `scratch/`, no `tmp/`. If something needs a home, it belongs *inside*
  a lab (each lab has its own `reference/`, `findings/`, `tools/`, etc.).
- **Never** add a loose file at the root other than the three coordinators above.
- To bring **new** work into the workspace, it must become **its own repo + submodule**
  — see *Adding a lab*. Do not "just drop it in" as a folder.
- A lab is referenced from another lab **by path** (e.g. `gamepad/` reads
  `../jangsjyro`), never by copying/vendoring its files into the root or into another
  lab. (Honors the repo rule: no absolute-path symlinks; reference by path or URL.)

This invariant is what makes the workspace cleanly separable, independently
cloneable per lab, and free of cross-lab contamination.

---

## Structure — the labs

All six top-level directories are submodules (`git submodule status` to see pinned SHAs):

| Lab (submodule) | Repository | Branch | Focus | Entry doc |
|---|---|---|---|---|
| `agent/` | [`JangMan-J/JangLabs-agent`](https://github.com/JangMan-J/JangLabs-agent) | `main` | Multi-agent coordination skills — the Convergent Arbiter skill package; ACP / Agent-Teams arbiter prompts. | `agent/CLAUDE.md` |
| `claude/` | [`JangMan-J/JangLabs-claude`](https://github.com/JangMan-J/JangLabs-claude) | `main` | The Claude Code harness for this box — hooks, `CLAUDE.md` fragment, settings; installed globally via `install.sh`. | `claude/CLAUDE.md` |
| `gamepad/` | [`JangMan-J/JangLabs-gamepad`](https://github.com/JangMan-J/JangLabs-gamepad) | `main` | Linux gamepad input (8BitDo Ultimate 2 / gyro / Steam-Input-vs-JSM). Depends on the `jangsjyro` sibling. | `gamepad/CLAUDE.md` |
| `jangsjyro/` | [`JangMan-J/jangsjyro`](https://github.com/JangMan-J/jangsjyro) | `branch-a-port` | The JangsJyro JoyShockMapper fork — the JSM source-of-record for `gamepad/`. C++23, upstream-facing. | `jangsjyro/AGENTS.md` |
| `proton/` | [`JangMan-J/JangLabs-proton`](https://github.com/JangMan-J/JangLabs-proton) | `main` | ProtonDB-driven Linux/Proton config inference (the `protondb-tuner` skill). | `proton/CLAUDE.md` |
| `theme/` | [`JangMan-J/JangLabs-theme`](https://github.com/JangMan-J/JangLabs-theme) | `main` | Data-first terminal→desktop color-role mapping (KDE, Kvantum, Kitty, Warp). | `theme/HANDOFF.md` |

`jangsjyro` is the model the others now follow: an independent repo, pinned by SHA,
never vendored into JangLabs history. The five `JangLabs-*` repos were fresh-init
extractions of formerly in-tree labs (their pre-extraction history lives in JangLabs'
own git log).

---

## Working in this repo

**Start at the lab boundary, not the repo root.** A task is almost always *inside one
lab*. The moment your work concerns a lab, that lab's own `CLAUDE.md` (or entry doc) is
the authority — see *Lab scoping*.

### Submodule mechanics

- **Clone:** `git clone --recurse-submodules <JangLabs-url>`. On an existing checkout
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
- **`gamepad` ↔ `jangsjyro` coupling:** `gamepad/` reads the JSM source at
  `../jangsjyro` (read-only, never vendored). That path only resolves inside a full
  JangLabs checkout, so do gamepad work here, not in a standalone `JangLabs-gamepad`
  clone.

### Adding a lab

1. Create the lab as its **own** git repo (`JangLabs-<name>`), push it to a remote.
2. `git submodule add -b <branch> <url> <name>` at the JangLabs root.
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
- **Don't cross lab boundaries.** Conventions in one lab (e.g. `gamepad/`'s real-runtime
  evidence rule) do not apply to another (e.g. `agent/`'s skill-prompt contract). Don't
  edit or import a sibling lab from inside one — reference it by path/URL if needed.
- **Resumable handoffs are sacred.** Where a lab has `handoffs/` or a `HANDOFF.md`, each
  is meant to let a fresh session pick up cold. Don't edit them casually.
- **Findings are append-only knowledge.** `findings/*.md` records non-obvious facts
  learned across sessions; add to them when a discovery would otherwise be lost.

### The automation (`lab-scope` hook)

The `claude/` harness ships `hooks/lab-scope.sh` (a `UserPromptSubmit` hook). It walks
up from the session's working directory to the `.claude-workspace` marker at the
workspace root; when found, it treats each top-level non-dot child as a lab and, **the
moment the active lab changes**, injects a one-paragraph scope banner naming the lab and
its entry doc. It is silent off-workspace and when the lab is unchanged, so it costs
nothing until you actually re-scope.

- **Enable it:** from `claude/`, run `./install.sh --apply`, then restart Claude Code
  (or `/reload-plugins`). It registers alongside the other harness hooks.
- **The marker** (`.claude-workspace`) is what flags this tree as a multi-lab workspace.
  Keep it at the root. The mechanism is generic — any future workspace that drops the
  same marker gets the same scoping behavior.

---

## Repo-level conventions

- **Branch for PRs:** `main` (in JangLabs and in each lab repo).
- **No build system at the workspace root.** Each lab manages its own dependencies
  (usually ad-hoc Python; some have their own `requirements.txt`).
- **Avoid absolute-path symlinks** — they break on clone. Reference other work by path
  (within a checkout) or by URL; never vendor a sibling lab's files.
- **Large binary artifacts** (screenshots, HID dumps, capture logs) live under the
  owning lab's `reference/` or `runs/`, never at the workspace root.
- **`.devcontainer/`** provides a reproducible container (Python 3.12 + uv + ruff +
  shellcheck + Node LTS); it is a dot-dir and is exempt from the lab rule.
