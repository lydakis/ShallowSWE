# DeepSWE CPSC amendment v0.4

Date: 2026-07-16

This amendment preserves `configs/deepswe-cpsc-v0.3.json` and every A1--A6 result. It records one
result-informed behavioral diagnostic and one reproducibility observation before public
circulation.

## A7: paired outcome-dispersion diagnostic

A follow-up discussion proposed that Luna max's broader observed task coverage might reflect more
varied attempt-level strategies than Sol max. Four binary attempts per task cannot identify that
mechanism. They can, however, test whether the two configurations have different task-level outcome
distributions.

The A7 diagnostic restricts the comparison to tasks with exactly four scored attempts for both
configurations. Luna max has 111 complete cells, Sol max has 112, and their intersection contains
110 tasks. For each configuration the analysis reports:

- tasks with zero, one to three, and four successes;
- the share of tasks with one to three successes;
- any-success task coverage; and
- a method-of-moments beta-binomial intraclass correlation estimated from the four-attempt success
  counts.

Using 10,000 paired task-cluster bootstrap replicates and seed `20260716`, the analysis estimates
Luna-minus-Sol differences in the middle-outcome share, coverage rate, and intraclass correlation.
The intervals vary the composition of the 110 observed complete tasks. They do not establish
generalization to unseen tasks or identify strategy diversity.

## Artifact-access observation

On 2026-07-16 the v1.1 release manifest and trial metadata advertised trajectories for the focal
GPT-5.6 configurations, but representative CloudFront trajectory URLs returned S3
`403 AccessDenied`. Adding the public site's `Origin` and `Referer` headers did not change the
response. A Fable 5 trajectory using the same manifest pattern returned HTTP 200, so the failure is
selective rather than a general CDN outage. The current `datacurve-ai/deep-swe` repository contains
the benchmark task packages but not the trial trajectories as an alternate access path.

The public report is tracked in
[`datacurve-ai/deep-swe#59`](https://github.com/datacurve-ai/deep-swe/issues/59), with an independent
reproduction from this analysis in
[`issuecomment-4988427711`](https://github.com/datacurve-ai/deep-swe/issues/59#issuecomment-4988427711).
Until the GPT-5.6 trajectories become accessible, diagnosis overlap, patch similarity, and strategy
pivot analyses remain unavailable.

## Editorial revision boundary

The paper adds A7 only as a post-hoc exploratory diagnostic in the benchmark-design discussion and
the limitations section. It does not promote task coverage, outcome dispersion, or strategy
diversity into the abstract, contribution map, or primary economic results.
