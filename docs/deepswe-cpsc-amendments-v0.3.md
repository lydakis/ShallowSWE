# DeepSWE CPSC amendment v0.3

Date: 2026-07-15

This amendment preserves `configs/deepswe-cpsc-v0.2.json` and every A1--A5 result. It records one
reviewer-requested, result-informed robustness analysis before public circulation.

## A6: repository-cluster sensitivity

DeepSWE v1.1 contains 113 tasks from 91 repositories. The primary uncertainty analysis resamples
task IDs, so it does not preserve possible dependence among multiple tasks from the same repository.
The task artifact shows 75 repositories with one task, 12 with two, three with three, and one with
five.

The A6 sensitivity samples 91 repository IDs with replacement. Every selected repository retains
all of its tasks and all scored attempts for those tasks. Using 10,000 replicates and seed 20260715,
the analysis recomputes:

- Sol high versus Sol max;
- Sol xhigh versus Sol max;
- Luna max versus Sol max;
- Luna max versus Sol high; and
- policy selection and no-eligible frequency at 70% and 75% reliability floors.

Pairwise outputs include solve-rate differences, CPSC ratios, agent steps, individual token
counters, their descriptive sum, and accumulated agent and trial seconds per verified success.
Percentile intervals measure sensitivity to repository composition within this suite. They do not
support generalization to unseen repositories, future models, or production workloads.

## Editorial revision boundary

The accompanying framing revision changes the title, abstract, result order, contribution map,
frontier terminology, and policy presentation. It moves the highest-pass family panel to the
appendix and adds compact reliability-floor and proxy-failure-charge tables. These presentation
changes do not add new estimands beyond A1--A6.
