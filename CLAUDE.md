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

- **Never** create a plain (non-submodule) directory at the root.
  No `assets/`, no `shared/`, no `scratch/`, no `tmp/`, no `build/`. If something needs
  a home, it belongs *inside* a lab (each lab has its own `reference/`, `findings/`,
  `tools/`, etc.). Regenerable cross-lab build output, if ever needed, goes in a
  git-ignored **dot-directory** (`.build/`) — a dot-dir needs no exception to this
  invariant. See *Repo-level conventions*.
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

All six lab directories are submodules (`git submodule status` to see pinned SHAs).
**Naming:** the submodule path is lowercase; its repo is that path PascalCased with a
`JangLabs-` prefix (`agent` → `JangLabs-Agent`).

| Lab (submodule) | Repository | Branch | Focus | Entry doc |
|---|---|---|---|---|
| `agent/` | [`JangMan-J/JangLabs-Agent`](https://github.com/JangMan-J/JangLabs-Agent) | `main` | Multi-agent coordination skills — the Convergent Arbiter skill package; ACP / Agent-Teams arbiter prompts. | `agent/CLAUDE.md` |
| `synapse/` | [`JangMan-J/JangLabs-Synapse`](https://github.com/JangMan-J/JangLabs-Synapse) | `main` | The Claude Code harness for this box — hooks, `CLAUDE.md` fragment, settings; installed globally via `agent-harness.py`. | `synapse/CLAUDE.md` |
| `jangsjyro/` | [`JangMan-J/JangLabs-JangsJyro`](https://github.com/JangMan-J/JangLabs-JangsJyro) | `branch-a-port` | The JangsJyro JoyShockMapper fork (C++23, upstream-facing). Also hosts the `gamepad/` input-research lab (8BitDo Ultimate 2 / gyro / Steam-Input-vs-JSM) as a subdir. | `jangsjyro/AGENTS.md` |
| `proton/` | [`JangMan-J/JangLabs-Proton`](https://github.com/JangMan-J/JangLabs-Proton) | `main` | ProtonDB-driven Linux/Proton config inference (the `protondb-tuner` skill). | `proton/CLAUDE.md` |
| `switchtail/` | [`JangMan-J/JangLabs-SwitchTail`](https://github.com/JangMan-J/JangLabs-SwitchTail) | `main` | SwitchTail — the operator's switchboard for agentic terminals: a Zellij plugin (Rust → WASM). Fresh-slate restart 2026-06-12; kitty era archived at tag `kitty-era-final` + `.archive/switchtail-kitty-era/`. Trunk-based on `main`. | `switchtail/CLAUDE.md` |
| `bolt/` | [`JangMan-J/JangLabs-Bolt`](https://github.com/JangMan-J/JangLabs-Bolt) | `main` | The routed-memory reseed: one self-contained `CORE-SPEC.md` distilling `synapse`'s splintered tag-routed memory subsystem back to a clean core (references synapse by path, never vendored). Scaffolded 2026-06-18. | `bolt/CLAUDE.md` |

`jangsjyro` is the structural model the others now follow: an independent repo, pinned
by SHA, never vendored into JangLabs history (it was the one lab already independent
before the others were extracted). The three others (`JangLabs-Agent`/`JangLabs-Synapse`/
`JangLabs-Proton`) were fresh-init extractions of
formerly in-tree labs (their pre-extraction history lives in JangLabs' own git log). All
repos share the `JangLabs-` name prefix (`jangsjyro`'s is `JangLabs-JangsJyro`).
`switchtail` (added 2026-06-10) was
likewise standalone-first: the cockpit toolkit migrated out of loose `$HOME` files into
its own repo, then wired in. (A
sixth, `JangLabs-Gamepad`, was likewise extracted but has since been folded into
`jangsjyro/gamepad/` and its submodule retired — its history remains in JangLabs' git log.
`JangLabs-Theme` was similarly extracted, then removed as a submodule on 2026-06-04 — its
repo remains on GitHub and its in-tree history lives in JangLabs' git log. `jangsjedi`, a
standalone-first lab added 2026-06-03 — the multi-claude orchestrator Rust workspace —
was removed on 2026-06-11 along with its GitHub repo `JangLabs-JangsJedi`; only the
submodule-pointer trail remains in JangLabs' git log.) `synapse` was
the `claude` lab until 2026-06-11, when the lab, its repo (`JangLabs-Claude` →
`JangLabs-Synapse`), and its memory taxonomy were renamed at GSD project initiation.

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

The `synapse/` harness ships `hooks/lab-scope.sh` (a `UserPromptSubmit` hook). It walks
up from the session's working directory to the `.claude-workspace` marker at the
workspace root; when found, it treats each top-level non-dot child as a
lab and, **the moment the active lab changes**, injects a one-paragraph scope banner naming the lab and
its entry doc. It is silent off-workspace and when the lab is unchanged, so it costs
nothing until you actually re-scope.

- **Enable it:** from `synapse/`, run `./agent-harness.py install --apply`, then restart
  Claude Code (or `/reload-plugins`). It registers alongside the other harness hooks.
- **The marker** (`.claude-workspace`) is what flags this tree as a multi-lab workspace.
  Keep it at the root. The mechanism is generic — any future workspace that drops the
  same marker gets the same scoping behavior.

---

## Handoffs

> **Informational — not authority over any lab.** This describes *where handoffs
> physically live* so they're discoverable when you launch from the root before picking a
> lab. It governs nothing inside a submodule: the moment your cwd enters `<lab>/`, that
> lab's entry doc is the authority (per *Lab scoping* above), and this note yields to it
> exactly as the rest of this root file does.

Session handoffs (from the `session-handoff` skill) are written to
`<launch-cwd>/.claude/handoffs/` — so a handoff lands in whichever lab (or this root, or
`$HOME`) you launched from. Because `.claude/` is git-ignored everywhere, these are
**untracked local scratch**, not committed history. That locality is intended (a lab's
handoffs stay with the lab), but it scatters them across many directories.

- **Per-lab scratch:** `<lab>/.claude/handoffs/` — the normal home for a handoff about
  that lab's work. Cross-lab / root-level handoffs go in `.claude/handoffs/` here.
- **One tracked exception:** `synapse/handoffs/` (no dot) holds committed *design-record*
  handoffs cited by `synapse/README.md` — an archive, not scratch. Leave it tracked.
- **Discovery:** `.handoff_index` at this root is a generated index of every handoff
  across all of the above plus `~/.claude/handoffs/`, **grouped by scope**: cross-lab,
  per-lab, box/unspecified, and stale. It's a git-ignored root dot-file (honors the
  *non-dot ⇒ submodule* invariant with no exception), regenerated each session by
  `synapse/hooks/handoff-index.sh`. Read it to find a handoff; don't hand-edit it.
- **Scope is by content, not directory.** Each handoff declares its bucket with a
  `<!-- handoff-scope: X -->` tag inside the file (`X` = `cross-lab` | `<lab>` | `box` |
  `stale`), set after *reading* it — because a handoff's real subject can differ from
  where it physically sits (e.g. a box-level tool handoff that happens to live under a
  lab). Untagged files are path-inferred and flagged `(inferred)` in the index; **to
  reclassify, edit the file's tag**, not the index. New handoffs should add the tag (the
  `session-handoff` skill writes them untagged, so they start as `(inferred)`).

---

## Repo-level conventions

- **Branch for PRs:** `main` (in JangLabs and in each lab repo).
- **No build *system* or build *output* at the workspace root** — each lab owns its
  own build/deps (usually ad-hoc Python; some have their own `requirements.txt`) and
  its own compiled output. If a future need calls for collecting cross-lab artifacts
  in one place, use a git-ignored **dot-directory** (`.build/`, namespaced per lab as
  `.build/<lab>/`): a dot-dir is already excluded by the "non-dot ⇒ submodule" rule,
  so it needs no exception — which is exactly why the former tracked `build/` dir
  (which did need one) was retired.
- **Avoid absolute-path symlinks** — they break on clone. Reference other work by path
  (within a checkout) or by URL; never vendor a sibling lab's files.
- **Large binary artifacts** (screenshots, HID dumps, capture logs) live under the
  owning lab's `reference/` or `runs/`, never at the workspace root.
- **`.devcontainer/`** provides a reproducible container (Python 3.12 + uv + ruff +
  shellcheck + Node LTS); it is a dot-dir and is exempt from the lab rule.
