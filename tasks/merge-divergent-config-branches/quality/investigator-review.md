# Investigator Review

Model-assisted QA only; this is not independent routine-engineer sign-off.

The review found that selected-field reconstruction could drop main-only and release-only state and
that copying one script rejected modular solutions. The prompt now defines full merge semantics, the
verifier copies the complete scripts tree, hidden fixtures preserve unrelated fields, and a control
rejects selected-field data loss.
