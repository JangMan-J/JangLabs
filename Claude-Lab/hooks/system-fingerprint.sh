#!/usr/bin/env bash
# UserPromptSubmit hook. Stdout becomes injected context for the turn.
# Cached 60s in /tmp so a burst of prompts doesn't re-shell.
set -u

CACHE=/tmp/claude-system-fingerprint.cache
TTL=60

if [ -r "$CACHE" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$CACHE") ))
  if [ "$age" -lt "$TTL" ]; then cat "$CACHE"; exit 0; fi
fi

kernel=$(uname -r 2>/dev/null || echo unknown)
session=${XDG_SESSION_TYPE:-unknown}
desktop=${XDG_CURRENT_DESKTOP:-unknown}

# Tool versions, only if present. Empty string if missing.
v() { command -v "$1" >/dev/null 2>&1 && "$1" --version 2>/dev/null | grep -m1 -E '[0-9]' | sed 's/^[^A-Za-z]*//' || true; }

zsh_v=$(v zsh)
git_v=$(v git)
pacman_v=$(v pacman)

# AUR helper detection — paru/yay/none. Don't assume.
if command -v paru >/dev/null 2>&1; then aur_helper=paru
elif command -v yay >/dev/null 2>&1; then aur_helper=yay
else aur_helper="(none installed)"; fi

{
  printf '<system-fingerprint>\n'
  printf 'os: Arch Linux\n'
  printf 'kernel: %s\n' "$kernel"
  printf 'session: %s | desktop: %s\n' "$session" "$desktop"
  printf 'shell: %s\n' "${zsh_v:-zsh ?}"
  printf 'pkg-mgr: %s (repos); aur-helper: %s — NOT apt/yum/dnf\n' "${pacman_v:-pacman ?}" "$aur_helper"
  printf 'boot: systemd-boot (NOT grub)\n'
  printf 'gpu: NVIDIA proprietary\n'
  printf 'git: %s\n' "${git_v:-git ?}"
  printf '</system-fingerprint>\n'
} | tee "$CACHE"
