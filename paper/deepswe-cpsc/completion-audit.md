# DeepSWE CPSC Working Paper Completion Audit

Date: 2026-07-14

## Deliverables

- Working paper source: `paper/deepswe-cpsc/main.tex`
- Circulation PDF: `paper/deepswe-cpsc/deepswe-cpsc-working-paper.pdf`
- Funding brief: `paper/deepswe-cpsc/funding-brief.md`
- Historical A1--A3 specification and plan: `docs/deepswe-cpsc-preanalysis.md` and
  `configs/deepswe-cpsc-v0.1.json`
- A4--A5 amendment supplement and executable plan:
  `docs/deepswe-cpsc-amendments-v0.2.md` and `configs/deepswe-cpsc-v0.2.json`
- Analysis and paper-asset modules: `src/shallowswe/deepswe_economics.py` and
  `src/shallowswe/deepswe_paper.py`
- Independent review materials: `paper/deepswe-cpsc/fable-cross-family-review.md` and
  `paper/deepswe-cpsc/gpt-5-6-pro-neutral-review-packet.md`

## Frozen outputs

- Analysis report SHA-256:
  `58ad3a0c8938007d053f81094623dce85d3a24a418ee8f31ce2e72e4e132dabe`
- Generated-asset manifest SHA-256:
  `e6958da33929e23d20635eecc53e899fdef6fe8341ab07966ad155cb77fe4472`
- Circulation PDF SHA-256:
  `c4e4abd2807a440e37e1a98f70ec8bdbb8e4a7e2fef49a029dd6c27190b18681`

Historical v0.1 plan SHA-256:
`245d45f87bec842c0d2bbc79630eba85f354b4b242c19cee799286d509a32152`.
Its original Markdown specification is
`25bb6d07bd005d5b049208f5faee45ff3a5296b1194d7aad4226ba2d30145f92`.
Executable v0.2 plan SHA-256:
`4fc0cc98331f1ba6b05d31cdfac841ca4e1b7f0b8a38d35f961aa0255b4a326d`.
Its A4--A5 amendment supplement is
`ea9c61cfefa218da7b02daeff50a958a6675935850671f4a8b2a0bc35f499942`.

The report was regenerated independently to a second path. The two files were byte-identical and
had the same SHA-256.

## Data and reconciliation checks

- 18,522 source trials accounted for.
- 18,396 scored trials included and 126 infrastructure-excluded rows audited.
- 21 scored missing-cost rows retained under the declared primary imputation.
- 41 official configuration aggregates reconciled within `3.6e-15`.
- 10,000 task-cluster bootstrap replicates run with seed `20260714`.
- Percentile and BCa Luna-Sol ratio intervals agree to rounding.
- All 820 configuration pairs exported with paired and matched solved-task diagnostics.
- All 820 configuration pairs exported across seven resource-intensity surfaces, including agent
  and trial seconds per success.
- One Sonnet 5 high row missing all step/token counters is disclosed; its configuration-metric
  totals are undefined and excluded from those ranks, ratios, and frontiers.
- Equal-task 113-task and common 111-task workload estimands exported under amendment A4.
- Full-panel, leave-one-family-out, and GPT-5.6 group-out panel-solvedness diagnostics exported.
- Retrospective full-basket and Sol-success proxy failure-charge diagnostics remain separate.
- The paired Luna-max versus Sol-high contrast is exported under amendment A5.
- Exclusions-as-failures with configuration-mean spend change no CPSC rank, frontier membership,
  or five-point reliability-floor winner.

## Verification

Focused analysis tests:

```text
uv run python -m unittest tests.test_deepswe_economics tests.test_deepswe_paper
Ran 20 tests: OK
```

Focused lint:

```text
uv run ruff check src/shallowswe/deepswe_economics.py \
  src/shallowswe/deepswe_paper.py tests/test_deepswe_economics.py \
  tests/test_deepswe_paper.py
All checks passed
```

Repository-wide test discovery ran 193 tests. It has one failure in the unrelated dirty-worktree
pilot-readiness slice:

```text
test_pilot_readiness.PilotReadinessTests.
test_manifest_freezes_revised_allocation_and_censoring_boundaries
AssertionError: report["structurally_valid"] is False
```

No DeepSWE analysis or paper test failed.

## Paper QA

- Tectonic compilation succeeded.
- The PDF has 12 physical pages in a single-column article layout. References end on page 11 and
  the compact reproducibility appendix occupies page 12.
- All 12 rendered pages were visually inspected.
- Figures have legible labels, units, uncertainty notes, and cohort context.
- Tables and figures were reconciled to generated CSV or JSON outputs.
- Citations resolve in the compiled PDF.
- Final Tectonic pass reports no overfull or underfull layout warnings; no content is clipped.

## Claim audit

- The paper states upfront that raw realized CPSC is recoverable from public aggregates.
- The estimand is named as realized benchmark spend per verified success under DeepSWE's attempt
  policy, not deployable retry cost.
- The primary result compares all 41 configurations and separates provider-reported invoice from
  measured agent-work surfaces.
- Luna-Sol is a same-provider price-versus-work case study, not the paper's sole finding.
- Sol effort levels provide a same-model case in which dollars and recorded resources move together.
- Luna max versus Sol high shows that effort tuning nearly erases the large Luna-versus-Sol-max
  invoice gap while substantially reducing recorded work and time.
- Equal-task weighting is a declared sensitivity and its exact 35% eligibility-boundary change is
  reported.
- Panel-solvedness is labeled retrospective; the GPT-5.6 analysis excludes all GPT-5.6 outcomes
  when assigning strata.
- Reliability floors, task matching, and Sol-derived proxy charges are labeled exploratory or
  post-outcome.
- The paper does not infer provider cost-to-serve, model size, margins, or model licensing.
- DeepSWE is presented as a transport study, not validation of another benchmark's construct,
  calibrated budgets, repair loop, or production decision policy.
