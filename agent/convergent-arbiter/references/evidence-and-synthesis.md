# Evidence And Synthesis

Convergent Arbiter compares evidence, not confidence.

## Evidence Types

Strong evidence:

- passing/failing validation commands
- repro steps that can be repeated
- focused tests that fail before and pass after
- minimal diffs tied to the root cause
- direct file references
- logs with relevant error lines
- project convention examples

Weak evidence:

- unverified claims
- broad summaries with no file references
- large diffs with unclear necessity
- speculative architecture arguments
- tests that pass but do not cover the objective

## Candidate Comparison

Score candidates qualitatively across:

- correctness against acceptance criteria
- validation result
- root-cause evidence
- minimality
- maintainability
- project convention fit
- test quality
- risk introduced
- coordination cost
- drift from objective

Do not automatically choose the largest or most elaborate patch. Prefer the smallest validated result that preserves future maintainability.

## Synthesis Patterns

Valid final outcomes:

- one candidate wins directly
- one implementation plus another worker's tests
- one implementation revised after review
- one plan selected after debate
- a new patch synthesized from selected evidence
- no code change, if evidence proves the correct outcome is explanation, configuration, or user action

## Resync Discipline

Preserve independence until a material discovery should change worker behavior.

Share:

- validated root cause
- accepted repro/test
- edge case
- failed approach to avoid
- ownership change
- high-level direction

Avoid sharing:

- raw speculation
- full competing patch unless it is meant to be reused
- every intermediate thought

## Final Validation

Before final response:

1. Ensure the final workspace contains only intended changes.
2. Run the strongest feasible validation.
3. Capture command, result, and any limitation.
4. Reconcile final diff against objective.
5. State remaining risk honestly.
