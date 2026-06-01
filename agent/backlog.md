# agent backlog

## High importance

### Verify model-version interfacability per CLI agent

Concern raised 2026-05-11: the arbiter spec currently treats a verified local CLI command as if all desired model versions behind that CLI are equally usable. That is not guaranteed. The same `codex` or `claude` binary may accept a model name syntactically while the provider account, backend routing, reasoning-effort options, context mode, tool/event surface, or provider profile rejects or degrades that specific `agent + model + config` tuple.

Required arbiter improvement:

- discover candidate model names separately from binary discovery
- probe each selected `agent + model + reasoning/config` tuple with a harmless non-edit task
- cache successful tuples in inventory with timestamps, CLI version, and failure notes
- prefer newest/strongest models only after runtime verification, or when the user explicitly requests the default
- record when a run intentionally relies on the CLI default rather than selecting a model

This matters because model selection is part of arbitration quality. A conservative known-working older model can satisfy "strong model" language, but it may miss the user's intent when the latest local default is stronger and available through the same CLI.
