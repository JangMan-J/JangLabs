# Claude-Lab

A Claude Code harness for this box. Five hook scripts + a CLAUDE.md fragment + a settings.json fragment, installed globally to `~/.claude/`. Designed to be cheap per turn, narrow in scope, and easy to remove.

## What it does

| Layer | Mechanism | Hook event | Cost per turn |
|-------|-----------|------------|---------------|
| Input grounding | `system-fingerprint.sh` injects 9 lines of immutable box facts (kernel, pacman/yay, systemd-boot, NVIDIA, etc.) | `UserPromptSubmit` | ~5ms cached |
| Pre-emptive redirection | `bash-idiom-guard.sh` blocks `apt`/`yum`/`grub-*`/`service`/`paru` etc. with a corrective message | `PreToolUse` (Bash) | ~5ms when fires |
| Output verification | `syntax-check-touched.sh` runs `jq empty` / `python -c ast.parse` / `bash -n` etc. on touched files | `PostToolUse` (Edit/Write/MultiEdit) | 10–100ms when fires |
| Secret-write block | `forbidden-files-guard.sh` blocks writes to `.env`, `*.key`, `*.pem`, `~/.ssh/`, `~/.gnupg/` | `PreToolUse` (Edit/Write/MultiEdit) | ~5ms |
| Config drift block | `config-drift-guard.sh` rejects settings.json edits that introduce `disableAllHooks` / `bypassPermissions` / silent `defaultMode` shifts | `PreToolUse` (Edit/Write/MultiEdit) | ~5ms |

A CLAUDE.md fragment adds: a verify-before-act rule, a memory-consultation rule, a `[Method]`/`[Fumble]` reflection-trigger rule for knowledge accretion, and an LSP-trust rule.

## What it deliberately does NOT do

- No `Stop` hook running a polyglot repo verifier (codex's package did this; wrong cost shape for sysadmin/dotfiles work).
- No Python interpreter spawn per tool call (pure POSIX-ish shell + jq).
- No CI workflow / pre-commit / Makefile additions.
- No silent mutation of `permissions.defaultMode` or any bypass flag.
- No MCP servers added.
- No skills pre-created. Skills should crystallize from observed Nth-session patterns, not anticipated ones.

## Install

```sh
./install.sh                 # dry-run: shows what would change
./install.sh --apply         # commit
```

Idempotent. Backups land in `Claude-Lab/.install-backups/<ts>/`. Restart Claude Code (or run `/reload-plugins`) afterward.

## Uninstall

```sh
./uninstall.sh               # dry-run
./uninstall.sh --apply       # commit
```

Removes the symlinks, the CLAUDE.md fragment block, and the hook entries from `settings.json`. Leaves `permissions.allow` / `permissions.deny` entries alone (they may have been amended after install).

## Files

| File | Role |
|------|------|
| `hooks/system-fingerprint.sh` | UserPromptSubmit — 9-line box fingerprint, cached 60s |
| `hooks/bash-idiom-guard.sh` | PreToolUse(Bash) — block non-Arch idioms |
| `hooks/syntax-check-touched.sh` | PostToolUse(Edit/Write) — narrow syntax verification |
| `hooks/forbidden-files-guard.sh` | PreToolUse(Edit/Write) — block secret-path writes |
| `hooks/config-drift-guard.sh` | PreToolUse(Edit/Write) — block settings weakening |
| `CLAUDE.md.fragment` | Appended to `~/.claude/CLAUDE.md` between sentinels |
| `settings.global.fragment.json` | Merged into `~/.claude/settings.json` (allow/deny + hooks) |
| `install.sh`, `uninstall.sh` | Idempotent dry-run-by-default |

## Iteration

Edit the source under `Claude-Lab/hooks/` directly — the symlinks point here, so changes are live. Re-run `install.sh --apply` only when changing the CLAUDE.md fragment or settings.json shape.

## Known limitations

- `bash-idiom-guard.sh` matches at command-start or after pipe boundaries, but a deeply-nested heredoc or process substitution containing `apt install` could slip past. The cost-of-false-negative here is "Claude tries `apt`, gets `command not found`, learns" — acceptable.
- `config-drift-guard.sh` pattern-matches the proposed file content. A semantically equivalent edit using JSON whitespace tricks could evade it. Not worth defending against (no one types `disableAllHooks: true` accidentally).
- The `system-fingerprint` cache lives in `/tmp` and survives reboots' worth of context, but `/tmp` is tmpfs on most setups so it does NOT survive reboot. Acceptable.
