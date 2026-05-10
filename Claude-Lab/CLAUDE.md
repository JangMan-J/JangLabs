# Claude-Lab — agent conventions

## What lives here

Hook scripts + CLAUDE.md fragment + settings fragment that together constitute the Claude Code harness for this box. Installed globally to `~/.claude/` via `install.sh`. See `README.md` for what each file does.

## Working in this lab

- **Hooks are live via symlink.** `~/.claude/hooks/<name>.sh -> Claude-Lab/hooks/<name>.sh`. Edit the source here; no re-install needed for hook script changes.
- **CLAUDE.md fragment and settings fragment require re-install.** After editing either, run `./install.sh --apply` to push to `~/.claude/`.
- **Hooks must be quiet on success.** The codex-package failure mode was walls of `[ok]/[skip]` lines feeding into Claude's context. Exit 0, no output. Reserve stderr for actionable failure.
- **Hooks must be cheap.** Pure POSIX-ish shell + jq. No Python interpreter spawn per tool call. If a hook is tempted to grow past ~50 lines, ask whether the leverage justifies it.
- **Test hooks before merging.** Run a script directly with a sample JSON input on stdin. Example for the bash-idiom-guard:
  ```sh
  printf '{"tool_input":{"command":"apt install foo"},"cwd":"/tmp"}' | ./hooks/bash-idiom-guard.sh; echo "exit=$?"
  ```

## What changes go where

| Change | Where |
|--------|-------|
| New hook script | `hooks/<name>.sh` + register in `settings.global.fragment.json` |
| New CLAUDE.md rule (global) | `CLAUDE.md.fragment` (between sentinels) |
| New global allow/deny entry | `settings.global.fragment.json` `permissions.allow`/`.deny` |
| Per-project allowlist | NOT here — that's `<project>/.claude/settings.json` |
| Skill (Nth-session pattern crystallization) | Use `skill-creator` plugin; place under `~/.claude/skills/` (out of this lab) |
| Finding (e.g. "hook X interacts unexpectedly with feature Y") | `findings/<topic>.md` (create dir on first finding) |

## Conventions to preserve

- **Idempotent install/uninstall** with dry-run default. The user runs auto mode by choice; surprising state changes are not acceptable.
- **Backups are per-run timestamped under `.install-backups/<ts>/` and `.uninstall-backups/<ts>/`.** Add these to `.gitignore` if not already.
- **No permission-mode mutation.** `install.sh` must never write `defaultMode`, `disableAllHooks`, `disableBypassPermissionsMode`, `disableAutoMode`, or any equivalent. The `config-drift-guard` enforces this from the runtime side; install.sh enforces it from the install side.
- **No skills pre-created.** Wait for a recurring pattern to crystallize across Nth sessions before promoting.
