# DeepSWE CPSC Working Paper Completion Audit

Date: 2026-07-16

## Deliverables

- Working paper source: `paper/deepswe-cpsc/main.tex`
- Circulation PDF: `paper/deepswe-cpsc/deepswe-cpsc-working-paper.pdf`
- Funding brief: `paper/deepswe-cpsc/funding-brief.md`
- Historical A1--A3 specification and plan: `docs/deepswe-cpsc-preanalysis.md` and
  `configs/deepswe-cpsc-v0.1.json`
- A4--A5 amendment supplement and executable plan:
  `docs/deepswe-cpsc-amendments-v0.2.md` and `configs/deepswe-cpsc-v0.2.json`
- A6 repository-cluster supplement and executable plan:
  `docs/deepswe-cpsc-amendments-v0.3.md` and `configs/deepswe-cpsc-v0.3.json`
- A7 paired outcome-dispersion and artifact-access supplement and executable plan:
  `docs/deepswe-cpsc-amendments-v0.4.md` and `configs/deepswe-cpsc-v0.4.json`
- Analysis and paper-asset modules: `src/shallowswe/deepswe_economics.py` and
  `src/shallowswe/deepswe_paper.py`
- Independent review materials: `paper/deepswe-cpsc/fable-cross-family-review.md` and
  `paper/deepswe-cpsc/gpt-5-6-pro-neutral-review-packet.md`

## Frozen outputs

- Analysis report SHA-256:
  `419ff9077e34c93870142578662d6353a40d9395d57e6b2fddd6a8b7985c4425`
- Generated-asset manifest SHA-256:
  `6d7fa6f569a043f14523993fc4aee339f84c1755b1da9771aea62309d4b980f8`
- Circulation PDF SHA-256:
  `780ddec59672e40339ad5f3f4675af79c78d089a3101bbfd375c6fef4ad56f43`

Historical v0.1 plan SHA-256:
`245d45f87bec842c0d2bbc79630eba85f354b4b242c19cee799286d509a32152`.
Its original Markdown specification is
`25bb6d07bd005d5b049208f5faee45ff3a5296b1194d7aad4226ba2d30145f92`.
Executable v0.2 plan SHA-256:
`4fc0cc98331f1ba6b05d31cdfac841ca4e1b7f0b8a38d35f961aa0255b4a326d`.
Its A4--A5 amendment supplement is
`ea9c61cfefa218da7b02daeff50a958a6675935850671f4a8b2a0bc35f499942`.
Executable v0.3 plan SHA-256:
`882bd0b8e8a3882f337477766b8ba015108694ce2c4390f174671b43efbc587f`.
Its A6 amendment supplement is
`19cf8b3f955169da534ee3d2ecb55ffac3a6bebefbfebff312af3f858aaaa1e5`.
Executable v0.4 plan SHA-256:
`64b6c2a0dda7f0ff4f61d49e4a8714e45303944f3c58a5d45a01bb52e3ffd9fa`.
Its A7 amendment supplement is
`cd9e6fda2224eceeb606a4f4e27ea548f6b15836341275669187b8f0b59d2952`.

The report was regenerated independently to a second path. The two files were byte-identical and
had the same SHA-256.

## Data and reconciliation checks

- 18,522 source trials accounted for.
- 18,396 scored trials included and 126 infrastructure-excluded rows audited.
- 21 scored missing-cost rows retained under the declared primary imputation.
- 41 official configuration aggregates reconciled within `3.6e-15`.
- 10,000 task-cluster bootstrap replicates run with seed `20260714`.
- 10,000 repository-cluster bootstrap replicates run with seed `20260715`; all tasks and attempts
  were retained within each sampled repository.
- 10,000 paired complete-task bootstrap replicates run with seed `20260716` on the 110 Luna-max
  and Sol-max tasks with exactly four scored attempts for both configurations.
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
- The four highlighted pairwise contrasts and the 70% and 75% policies are re-estimated under
  repository clustering in amendment A6.
- The A7 paired diagnostic resolves a 20.9-point middle-outcome-share difference and a lower
  intraclass correlation for Luna, while its 4.5-point coverage difference remains unresolved.
- The A7 output is exported as `generated/tables/paired-outcome-dispersion.csv`; binary outcomes are
  explicitly insufficient to identify strategy diversity.
- Hidden filesystem metadata such as `.DS_Store` is excluded from the generated-asset manifest.
- Exclusions-as-failures with configuration-mean spend change no CPSC rank, frontier membership,
  or five-point reliability-floor winner.

## Verification

Focused analysis tests:

```text
uv run python -m unittest tests.test_deepswe_economics tests.test_deepswe_paper
Ran 23 tests: OK
```

Focused lint:

```text
uv run ruff check src/shallowswe/deepswe_economics.py \
  src/shallowswe/deepswe_paper.py tests/test_deepswe_economics.py \
  tests/test_deepswe_paper.py
All checks passed
```

Repository-wide discovery was not rerun for this paper-only revision. The focused analysis and
paper-asset scope passed.

## Paper QA

- Tectonic compilation succeeded.
- The PDF has 13 physical pages in a single-column article layout. References and the descriptive
  appendix occupy pages 11--12; the reproducibility appendix starts cleanly on page 13.
- Changed pages 10, 11, and 13 were rendered at 144 DPI and visually inspected.
- Figures have legible labels, units, uncertainty notes, and cohort context.
- Tables and figures were reconciled to generated CSV or JSON outputs.
- Citations resolve in the compiled PDF.
- Final Tectonic pass reports no overfull or underfull layout warnings; no content is clipped.

## Claim audit

- The paper states upfront that raw realized CPSC is recoverable from public aggregates.
- The estimand is named as realized benchmark spend per verified success under DeepSWE's attempt
  policy, not deployable retry cost.
- The title and conclusion frame the contribution as identification of an operational
  recommendation, not invention of CPSC or denial that the observed rankings are mathematically
  well-defined.
- The primary result leads with the within-Sol effort ladder, then separates provider-reported
  invoice from measured agent-work surfaces across all 41 configurations.
- Luna-Sol is a same-provider price-versus-work case study, not the paper's sole finding.
- Sol effort levels provide a same-model case in which dollars and recorded resources move together.
- Luna max versus Sol high shows that effort tuning nearly erases the large Luna-versus-Sol-max
  invoice gap while substantially reducing recorded work and time.
- Repository clustering preserves the Sol effort result, Luna-Sol reversal, Luna-Sol-high parity
  interval, and high-floor feasibility warning.
- Luna's paired task outcomes are described as less polarized, not as evidence of a chaotic attempt
  process or greater strategy diversity.
- The descriptive five-task coverage edge is not promoted because its paired bootstrap interval
  includes zero.
- The selective GPT-5.6 trajectory `403 AccessDenied` result, Fable 5 HTTP 200 comparison, and
  upstream issue are dated and recorded in A7.
- Equal-task weighting is a declared sensitivity and its exact 35% eligibility-boundary change is
  reported.
- Panel-solvedness is labeled retrospective; the GPT-5.6 analysis excludes all GPT-5.6 outcomes
  when assigning strata.
- Reliability floors, task matching, and Sol-derived proxy charges are labeled exploratory or
  post-outcome.
- The paper does not infer provider cost-to-serve, model size, margins, or model licensing.
- DeepSWE is presented as a transport study, not validation of another benchmark's construct,
  calibrated budgets, repair loop, or production decision policy.
