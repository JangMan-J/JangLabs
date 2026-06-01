# Aegis Handoff

Project state lives in the top-level [`HANDOFF.md`](../../HANDOFF.md). Read that
first. This note only records the aegis-level framing.

## Where the project is

Theme-Lab pivoted from a screenshot/manual-capture methodology to a
**source-driven** mapper: terminal scheme source files → deterministic virtual
canvas → comparable fingerprint → correlation to KDE/Kvantum config fields.
Screenshots survive only as a one-time Gate 2 calibration check (Python
Playwright + Pillow), not as the research loop.

The screenshot-era artifacts, tools, and work logs were removed once that
methodology was retired; their durable conclusions are preserved under
`findings/` and the full history remains in git.

## Most relevant records

- `work/2026-05-28-arc-dark-cross-theme/HANDOFF.md` — the pivot rationale and
  the Arc Dark source/render correlation that motivated weighted nearest-neighbor
  scoring over exact matching.
- `baseline/2026-05-28-initial-baseline.md` — original project shape.

## Validation

```bash
python -m unittest discover -s tests
```
