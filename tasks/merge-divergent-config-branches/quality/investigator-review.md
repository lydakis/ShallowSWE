# Investigator Review

Model-assisted QA only; this is not independent routine-engineer sign-off.

The review found that selected-field reconstruction could drop main-only and release-only state and
that copying one script rejected modular solutions. The prompt now defines full merge semantics, the
verifier copies the complete scripts tree, hidden fixtures preserve unrelated fields, and a control
rejects selected-field data loss.

Fable and Grok advisory review found that the original wording implied a real Git merge and
overstated the horizon. The task now accurately describes snapshot reconciliation and records the
observed small scope without changing merge behavior.

The frozen v0.3 pilot still records this task as Workflow/large. Under the v0.4.2 work-product
contract, the submitted implementation of `scripts/apply_task.py` makes it a Code task, and its
later N=3 floor result indicates small pressure. A future panel revision must rework or replace this
slot while preserving the balanced matrix; this contract-only repair does not rewrite the frozen
pilot allocation.
