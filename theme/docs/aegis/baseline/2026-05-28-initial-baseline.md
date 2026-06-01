# Initial Baseline

## Project Shape

Theme-Lab is a data-first lab for mapping desktop and terminal theme colors to
stable semantic roles.

## Current Authority

- `CLAUDE.md` defines repository conventions: raw screenshots under
  `reference/captures/`, generated artifacts under `derived/`, durable
  conclusions under `findings/`, small CLI tools under `tools/`, and structured
  JSON preferred for sample data.
- `README.md` defines the objective, capture naming convention, Catppuccin
  calibration model, and current manual workflow.
- `config/capture-plan.json` defines initial capture scope and GUI/terminal
  state scenarios.
- `config/roles.json` defines GUI and terminal semantic roles plus the known
  Catppuccin GUI-only accent axis.
- `samples/points-template.json` defines the point-map shape used by
  `tools/sample-points.py`.
- `findings/catppuccin-accent-axis.md` records the working model that terminal
  palettes do not reliably identify GUI accent variants.
- `tests/test_sample_points.py` currently tests sampler mechanics, not full
  color scheme mapping scenarios.

## Validation

The current validation command is:

```bash
python -m unittest discover -s tests
```

At baseline creation, the suite contains two sampler tests and passes.
