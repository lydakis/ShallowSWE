# Investigator Review

Model-assisted QA only; this is not independent routine-engineer sign-off.

This task replaced a saturated status-parity candidate. Historical evidence records a legitimate
model miss, 0/2 floor passes, and 1/1 ceiling pass. QA tightened calendar-date validation, non-empty
legacy row numbering, decimal half-up rounding, cross-source precedence, reject ordering, status
aliases, normalized IDs, and the required CSV-only regression test. Nine bad implementations are
executed as negative controls.

Fable and Grok advisory review then exposed that date output normalization and multi-defect reject
precedence were only encoded by the verifier. The prompt now states both rules explicitly.
