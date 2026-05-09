# ArchLinux-Lab

Personal Arch Linux install plan, rendered as a single self-contained HTML document.

## Contents

| File | What it is |
|------|------------|
| `claudes-arch_linux-install.html` | Hand-crafted, dark-themed install guide. Covers Ventoy USB → Arch ISO boot → install. Subject system: laptop with RTX 4090, btrfs + snapshots, Steam-dependent workload. |

## Shape

- **HTML-first.** No source markdown exists; the HTML is authored directly.
- **Static.** No JavaScript, no interactivity beyond manual copy-paste of command blocks.
- **External CDN dep:** Google Fonts (`fonts.googleapis.com`) — the document degrades gracefully offline but loses its typography.

## Editing

Edit the HTML directly. There is no build step and no source-of-truth markdown to regenerate from. The CSS uses semantic classes (`phase`, `phase-header`, `cmd-block`, `warn`, `ref-card`) — preserve them when adding sections.

## What's missing

- No version or last-updated timestamp inside the document.
- No companion notes file capturing *why* specific choices were made (e.g. why btrfs+snapshots, why Ventoy). If those decisions need durable context, add a `notes.md` here.
