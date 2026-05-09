# Design: Claude Code Workflow Reference Doc

**Date:** 2026-04-18
**Status:** Approved design; awaiting implementation plan
**Target deliverable:** `%USERPROFILE%\Claude\WORKFLOW.md`

## Goal

Build a living reference doc that captures the Claude Code skills, agents,
and tools most relevant to this user's work (Steam Input / controller
research, Python tool building, multi-session investigations) so the user
can:

- Rapidly look up "I want to do X — what should I reach for?" during
  active work.
- Build working vocabulary around Claude Code features without wading
  through platform docs.
- Re-read the doc 6+ weeks from now and still get value — the doc is
  designed for returning readers, not first-pass skimmers.

Scale: roughly 2500–4000 words total. Terse, action-oriented,
second-person voice.

## Non-goals

- Not a replacement for Claude Code platform documentation. The reader
  can click through to official docs when they need deeper reference.
- Not an exhaustive catalog of every Claude Code feature. Features that
  are not relevant or not valuable to this user's work either live in
  the appendix as one-liners or get cut entirely.
- Not a general introduction to Claude Code. Assumes the reader has
  already used the tool for several weeks and is building on that base.

## Overall structure

1. **Top-of-doc decision table** — action-oriented lookup
   ("I want to… → reach for §N"), roughly 15–20 rows covering the
   highest-frequency situations.
2. **Three themed groups × four entries = twelve core deep-dives.**
3. **Appendix** — one-liners pointing at features not covered in depth,
   so the reader knows what exists without the doc bloating.

## The core twelve

### §1–4 Context & parallelism

1. **Subagents** — general-purpose, Explore, Plan, specialized.
   Context isolation, when the isolation cost pays off, parallel
   dispatch in a single message.
2. **Plan mode** — multi-step scaffolding before implementation.
   How it differs from ad-hoc deliberation.
3. **Background bash + Monitor** — long-running probes and captures
   without blocking the chat. Context-minimizing alternative to
   blocking-and-polling.
4. **Worktrees** — experimental tool variants without polluting the
   main workspace.

### §5–8 Workflow scaffolding

5. **Skills** — the superpowers library plus built-ins. Discovery,
   invocation, when each applies.
6. **`.claude/commands/`** — personal slash commands for prompts the
   user ends up repeating across sessions.
7. **Fast mode** — `/fast`, Claude Opus 4.6 with faster output.
   When to switch in and out.
8. **Visual companion** — browser-based companion for mockups,
   diagrams, comparisons. When seeing beats reading.

### §9–12 Persistence & continuity

9.  **CLAUDE.md layering** — global `~/.claude/CLAUDE.md` plus
    workspace `Claude/CLAUDE.md`. Precedence rules, where each kind
    of rule belongs.
10. **Auto-memory** — what is persisted, the user/feedback/project/
    reference organization, how to steer what gets saved.
11. **Handoff / BACKLOG pattern** — the user's own invention in this
    workspace. What makes a good handoff, when to promote a backlog
    item, how handoff docs stay self-contained.
12. **Hooks** (settings.json) — automated behaviors
    ("from now on when X, do Y"). When to reach for hooks vs. memory
    vs. CLAUDE.md.

## Entry template

Each deep-dive is roughly 150–250 words and uses the following
structure. Fields appear as short sub-headings so the doc is
skimmable on re-read.

- **What it is** — one or two sentences.
- **When to reach for it** — bullet list of trigger situations.
  This is the part the returning reader will actually scan.
- **How to invoke** — command, syntax, tool name, or slash command.
- **Gotchas** — specific things that trip people up. Prefer
  concrete warnings over generic "be careful" wording.
- **Example from this workspace** — a concrete tie-in to the user's
  Steam Input / gyro / handoff work so the pattern sticks.

## Decision table

Two columns: *"I want to…"* → *"Reach for… (§N)"*. Roughly 15–20 rows.

Seed rows (final list determined during implementation):

| I want to…                                                    | Reach for…                          |
|---------------------------------------------------------------|-------------------------------------|
| Run several independent research queries without context bloat | Parallel subagents (§1)             |
| Pause a long gyro capture without blocking the chat            | Background bash + Monitor (§3)      |
| Resume an investigation in a fresh session                     | Handoff doc (§11)                   |
| Try a risky refactor without wrecking the main workspace       | Worktree (§4)                       |
| Scaffold a multi-step tool build before committing to code     | Plan mode (§2)                      |
| Repeat a prompt I use every few sessions                       | Personal slash command (§6)         |
| See two mockups side-by-side before choosing                   | Visual companion (§8)               |
| Have Claude remember a preference between sessions             | Auto-memory (§10)                   |
| Enforce a behavior automatically without prompting each time   | Hook in settings.json (§12)         |

## Appendix (one-liners)

Short pointers to features the doc does not cover in depth, so the
reader knows they exist:

- MCP servers
- Scheduled agents / cron
- TodoWrite / task tracking
- Permissions / settings.local.json
- Keybindings
- Specialized skills (code-review, frontend-design, simplify, etc.)
- `/clear` and session boundaries
- WebSearch / WebFetch (already covered by a rule in CLAUDE.md)

## Style conventions

- Terse, second-person, active voice.
- Inline code for commands, paths, and tool names.
- Short rationale on non-obvious choices; no marketing language.
- Each entry self-contained — the reader should be able to land on
  one and get value without reading its neighbors.

## Cross-reference back from CLAUDE.md

Add one line to `%USERPROFILE%\Claude\CLAUDE.md` under
"Project layout":

> - `WORKFLOW.md` — personal reference for Claude Code skills,
>   agents, and tools most relevant to this workspace's work.

No behavioral rules move out of CLAUDE.md. WORKFLOW.md is reference
material; CLAUDE.md remains the authority on conventions.

## Maintenance posture

Treat WORKFLOW.md as a living document. When the user hits a friction
point that a workflow pattern would have addressed, update the
relevant section or add a new entry. Appendix items can be promoted
to core deep-dives as they prove valuable in practice. Conversely, if
a core pattern turns out to be rarely used, demote it to the
appendix rather than letting it stale in place.

## Out of scope (explicit)

- Any rewrite of CLAUDE.md beyond the one-line pointer.
- Tooling to auto-generate the doc from platform documentation.
- Formal process enforcement (for example, hooks that check
  "did you reach for the pattern the doc suggests?").
