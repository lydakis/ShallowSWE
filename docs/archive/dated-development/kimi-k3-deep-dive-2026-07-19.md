# Kimi K3 DeepSWE deep dive, 2026-07-19

This is a research checkpoint over a frozen DeepSWE v1.1 snapshot and already-published public
benchmark material. It uses no newly generated model outcomes. It does not amend the paper,
website, or benchmark. The note distinguishes observed outcomes, derived results, exploratory
interpretations, and unresolved mechanisms.

## Frozen evidence

The snapshot reports `generated_at=2026-07-17T08:18:55.870582+00:00`.

| Artifact | Bytes | SHA-256 | Use here |
| --- | ---: | --- | --- |
| `trials.json` | 32,913,393 | `6c010fb3e03c7eafc189be320b17ff4aaaf07d40a5910c81992d83aa155a2802` | Outcomes, cost, time, and launch timestamps |
| `tasks.json` | 57,634 | `bae967f6472943564c3fc5232fba3c8e0ac465c1be5ccf9dd4895d4ee9df6242` | Repository, language, prompt, and task metadata |
| `leaderboard-live.json` | 54,868 | `050663ae245106a7fc59312565059f46bd6ee10fa587131dd09a5062af5ed24d` | Snapshot identity only |

The task fingerprint filters `source=deep-swe` and `included_in_score=true`, uses seed `20260719`,
30,000 repository-cluster bootstrap replicates, and 200,000 wild-cluster replicates. Its primary
matched cohort has 111 tasks with four scored runs each for Kimi K3 max, GPT-5.6 Sol high, Claude
Fable 5 xhigh, and Grok 4.5 high, grouped into 89 repository clusters. The Luna and Terra
difficulty geometry is complete for 109 of those tasks.

The frozen derived inputs to this note are:

- `configs/analyses/kimi-k3-frontier-retrospective-2026-07-19/spec.json`, SHA-256
  `35790b99b75c03fa0a18d8ac778e77971fd2d9d0b76ac2aafc29d29426deba28`.
- `/tmp/deepswe-k3-task-fingerprint.md`, SHA-256
  `c7488dec8a6de47b73453abd0d59ccb36e36be32c8f41ba5982d24a7ab3b1784`.
- `/tmp/deepswe-k3-task-fingerprint.json`, SHA-256
  `97277842b5babce51f9f82c173066347b7ef87ef9e82488cc1644788ff2c2d6b`.
- `/tmp/deepswe-k3-attempt-dynamics.json`, SHA-256
  `13f941e9f8f009517ef8d11656f24542a933a5a4e2a3ad815936f8570f124d7d`.
- `/tmp/k3-task-traits.json`, SHA-256
  `70e13c48f369e65940a5b0402c1f39476669008af8ca4752ca134c480f8b64b0`.
- `/tmp/deepswe-policy-frontier.json`, SHA-256
  `49081f0fb56d76a360957bdffa34e509893a3e72e90c4d9752e746d80c194344`.
- `/tmp/deepswe-policy-pair-bootstrap.json`, SHA-256
  `52cd048d12f17aaf9f506ba9903b5f3837212c0ce262e93c7d0736ef32639639`.
- `/tmp/deepswe-policy-luna-terra.json`, SHA-256
  `6f2e13384385818996f6cd0fea5bd01129004c845358882bf4113847359cfd9e`.
- `/tmp/deepswe-k3-complete-report.json`, SHA-256
  `eafa63bcbdf59b7a6ac4e8d154f1d3330cf97ec81f67e66878d13be28092b66b`.
- `/tmp/deepswe-policy-near-optima-bootstrap.json`, SHA-256
  `d34b75668af2deb06dc71a00a10be8cca9b88d047270b3b31c2adab84321bb84`.
- `/tmp/k3-failure-geometry.json`, SHA-256
  `76e8f33bb1a66d172a708bfabd28fbc183aed57b2c51d4bb74a782ac2509a04f`.

Two paid diagnostics began before the scope was corrected. A six-request cache probe cost
`$0.062832`; an interrupted `ofetch` attempt cost `$2.0142822` and ended before a verifier result.
Both are excluded from every research result below. No new model outcome is part of this note.

## Where K3 sits in the full frontier panel

The live headline is accurate but incomplete: K3 is in the frontier capability cluster, not at its
economic frontier. Across all 451 scored K3 attempts it passes 309, or 68.51%, with a reported mean
estimated cost of $4.655 and realized CPSC of $6.794. In the frozen economic report it ranks eighth
of 44 effort configurations on pass rate, twentieth on CPSC, and is not on the attempt-cost Pareto
frontier. Sol high and Luna max are on that frontier.

The cleanest broad comparison uses the 108 tasks with four scored attempts for all eight focal
configurations:

| Configuration | Pass rate | Tasks solved at least once | Mean reported cost | CPSC | Retry ICC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kimi K3 max | 68.98% | 96/108 | $4.499 | $6.523 | 0.380 |
| GPT-5.6 Sol high | 69.21% | 93/108 | $3.355 | $4.847 | 0.489 |
| GPT-5.6 Sol xhigh | 69.91% | 92/108 | $4.586 | $6.561 | 0.567 |
| GPT-5.6 Sol max | 71.99% | 92/108 | $8.061 | $11.198 | 0.575 |
| GPT-5.6 Terra max | 68.98% | 95/108 | $4.804 | $6.964 | 0.488 |
| GPT-5.6 Luna max | 66.90% | 97/108 | $2.934 | $4.385 | 0.355 |
| Claude Fable 5 xhigh | 69.91% | 96/108 | $12.985 | $18.575 | 0.509 |
| Grok 4.5 high | 54.63% | 84/108 | $2.386 | $4.368 | 0.471 |

Repository-bootstrap intervals for K3's attempt pass-rate difference cross zero against Sol high,
Sol xhigh, Sol max, Terra max, Luna max, and Fable xhigh. Only the 14.35-point lead over Grok is
resolved in this eight-model basket, with interval 7.18 to 21.33 points. The data therefore place
K3 inside a statistically crowded frontier group.

Sol high point-dominates K3 on pass rate, reported cost, CPSC, steps, output tokens, and elapsed
time, but not on observed task coverage. Luna max is the more uncomfortable retry comparator: it
has lower pass@1 than K3, yet covers one more of the 108 tasks at lower reported cost. K3 is not the
unique route to broad retry coverage.

## Observed capability shape

On the 111-task matched cohort:

| Configuration | Passes | Pass rate | Tasks solved at least once | Random-subset pass@2 | Random-subset pass@4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kimi K3 max | 307/444 | 69.14% | 99/111, 89.19% | 82.58% | 89.19% |
| GPT-5.6 Sol high | 311/444 | 70.05% | 96/111, 86.49% | 80.63% | 86.49% |
| Claude Fable 5 xhigh | 313/444 | 70.50% | 99/111, 89.19% | 80.78% | 89.19% |
| Grok 4.5 high | 240/444 | 54.05% | 86/111, 77.48% | 67.42% | 77.48% |

**Observed and derived result:** K3 has fewer raw passes than Sol and Fable but covers more task
identities than Sol and the same number as Fable. Its successes are less redundant across the four
attempts. The random-subset interpolation therefore gives K3 higher pass@2 than both despite its
lower pass@1. This curve averages subsets of the four observed attempts; it is not a forecast for
additional retries.

**Observed outcome:** Pairwise any-success discordance favors K3 over Sol on 11 versus 8 tasks,
ties Fable at 4 versus 4, and favors K3 over Grok on 18 versus 5. However, K3 adds no task beyond
the observed Fable-plus-Grok union, while that union adds seven beyond K3. The union comparison
uses eight comparator attempts against four K3 attempts, so it is descriptive, not budget matched.
No K3-only task remains after unioning Sol, Fable, and Grok; their union contains ten tasks K3
never solves in this cohort.

Against Sol and Fable together, K3 alone reaches just one task, and only one of its four attempts
passes there. K3 misses three tasks both comparators reach. Individual task labels are noisy at
four attempts, so the stronger evidence is the aggregate failure geometry below.

Across the 108-task eight-model cohort, no model has an absolutely unique solved task. A
cost-agnostic Shapley decomposition of the all-model solve union gives K3 the second-highest
contribution to full-suite coverage, 13.00 percentage points, behind Fable's 13.36 and just ahead
of Luna's 12.86; their bootstrap intervals overlap. This is consistent with useful
complementarity, but it is not evidence that K3 is a uniquely necessary portfolio member.

## Exploratory task geometry

**Exploratory result:** On the 35 tasks where Luna plus Terra achieve at most four successes in
eight attempts, K3 leads Sol by 15.00 percentage points. On the other 74 tasks, it trails Sol by
7.77 points. The 22.77-point interaction has a repository-bootstrap 95% interval from 7.29 to
38.46 points and Holm-adjusted `p=0.0180`.

That result is not a generic claim that K3 is better on hard tasks. When Fable plus Grok defines
the hard stratum, K3 trails Sol there by 4.79 points. In the full two-by-two reference geometry,
K3 leads Sol by 37.50 points on the ten tasks hard for Luna plus Terra but not Fable plus Grok,
while trailing by 17.05 points on the 22 tasks with the reverse pattern. The contrast between
those contrasts is 54.55 points, with bootstrap interval 26.67 to 83.38.

**Exploratory interpretation:** The defensible hypothesis is family-specific complementarity.
K3 appears to fail on a different task surface from some frontier families. The outcome table does
not identify the mechanism.

The residual task geometry adds an important qualification: K3 is most similar to Fable, not most
different from it. After regressing each pair's four-attempt task success rates on the mean of the
other six focal configurations, the K3-Fable residual correlation is `0.614`, with repository-
bootstrap interval `0.473` to `0.734`. Fable is K3's closest residual neighbor in 99.99% of
repository bootstrap samples. Using one shared difficulty control built from 22 other complete
configurations leaves the result at `0.625`, interval `0.494` to `0.743`. Grok is a distant second
under the pair-specific control at `0.223`, interval `0.062` to `0.372`, Holm-adjusted `p=0.0143`.

**Exploratory interpretation:** K3 and Fable tend to overperform and underperform on the same task
identities after general difficulty is removed. That supports K3 as a lower-reported-cost substitute
for Fable, not a strong complement to Fable. An apparent negative K3-Sol-xhigh residual correlation
depends on the difficulty-control construction and is rejected.

**Exploratory metadata checks:** No task-metadata interaction survives Holm correction across the
expanded 28-feature family. Metadata-only leave-one-repository-out models have negative
out-of-sample R-squared against both the K3-minus-Sol and K3-minus-Fable task deltas. Go is the
largest language interaction against Fable, but its adjusted `p=0.164` is not close to the expanded
family threshold. Prompt length is unrelated to K3 all-failure, with a 1.029 geometric-mean ratio
and randomization `p=0.854`. The artifact exposes only eight task fields and no issue body, changed
files, tests, patch, task date, or category, so richer task-type claims are unavailable.

The twelve K3 all-fail tasks occur in twelve different repositories, which argues against one
repository cluster driving the result. They are materially harder for the other model panel too:
the external-reference pass rate is 22.2% on K3 all-fails versus 47.2% elsewhere, with
repository-clustered `p=0.000183`. The available metadata cannot explain which hard tasks K3 will
miss.

## Observed retry dependence

The retry-dependence analysis uses the 108 tasks with complete four-attempt cells across its full
frontier comparison. For K3, the within-task exchangeable intraclass correlation is `0.380`, with
task-bootstrap interval `0.254` to `0.497`. Four same-task attempts have a design effect of `2.139`
and only about `1.87` effective independent attempts for estimating a mean.

**Observed derived result:** K3's order-neutral solve curve is 68.98%, 82.25%, 86.81%, and 88.89%
for one through four attempts. Marginal coverage is 68.98, 13.27, 4.55, and 2.08 points. The
conditional success yield among tasks still unresolved before each attempt falls from 68.98% to
42.79%, 25.65%, and 15.79%.

The independent-attempt formula would predict 99.07% pass@4 from the marginal pass rate, but the
observed pass@4 is 88.89%. It would predict about one all-fail task and 24.45 all-pass tasks;
the cohort has 12 all-fail and 44 all-pass tasks. Repeats are useful, but they are strongly
correlated and should not be priced or powered as independent draws.

K3 is less task-clustered than Sol high and Fable xhigh in point estimates. Of the 108 fully matched
tasks, K3 has 52 with one to three successes, versus 41 for Sol high and 40 for Fable. Its ICC is
0.380 versus 0.489 and 0.509. The paired repository-bootstrap intervals for the ICC differences
still cross zero, narrowly so against Fable. Luna max has an even lower ICC of 0.355 and 57
intermediate tasks. The defensible claim is lower observed retry redundancy than several peers,
not uniquely diverse K3 strategies.

## Observed time and timeout shape

Across all 451 scored K3 rows, 309 pass, for the official 68.51% pass rate. Agent duration has
median 3,972.9 seconds, p90 7,636.2 seconds, and p95 9,389.0 seconds. Ten failures land at the exact
three-hour cap, or 2.22% of scored attempts. No other frontier profile in this analysis has an
exact three-hour cap.

The ten caps form two descriptive phenotypes:

- Nine low-throughput caps span seven tasks and record 8 to 29 steps, or 2.67 to 9.67 steps/hour.
- One active-throughput cap on `dynamodb-toolbox-lazy-recursive-schemas` records 230 steps,
  76.67 steps/hour, and 140,698 output tokens.

The gap between 9.67 and 76.67 steps/hour is the largest adjacent split among the ten capped rows,
but it does not locate the waiting. Historical counters omit any final response still in flight at
cutoff. A low recorded step count cannot distinguish provider delay, network delay, harness retry,
task execution, or one very long generation.

The capped rows cover eight tasks. The other 21 K3 attempts on those tasks pass only 8 times,
38.10%, so this selected set is difficult for K3 even outside the caps. The official pass rate is
69.91% after excluding the nine low-throughput caps and 70.07% after excluding all ten. Even the
upper bound that changes every cap to a pass is 70.73%. The cap anomaly matters operationally but
does not explain the full capability result.

After dropping the nine low-throughput caps, the median paired-task K3 duration is 3.16 times
Fable's and 7.33 times Sol's. K3 records 1.45 times Fable's steps and 2.60 times Sol's, while each
step takes 2.15 times and 2.70 times as long, respectively. Slow wall time is therefore broader
than the ten exact caps.

## Exploratory chronology and concurrency signal

The first 200 scored K3 attempts launch in the same minute. They pass at 65.00% and include seven
caps. The later 251 pass at 71.31% and include three caps. The cap risk ratio is 2.93, but the
two-sided Fisher test is `p=0.116`; a within-task randomization check is `p=0.083` two-sided. This
is suggestive, not statistically conclusive.

Across the 112 tasks with four scored K3 attempts, chronological slot pass rates rise from 64.29%
to 66.07%, 71.43%, and 73.21%. The unadjusted within-task trend test is `p=0.0441`, but K3 is one of
eight frontier trend checks and no family-wise adjustment was prespecified. Excluding all exact
caps weakens it to `p=0.0593`. Slots one and two are usually launched within a second, while median
gaps to slots three and four are about 3,402 and 2,562 seconds. Calendar time, workload, attempt
slot, launch cohort, and estimated concurrency are inseparable in this run.

## Cost accounting changes the interpretation

Every K3 row's cache counter is a rounded 98% of its input counter. That is an imputation, not
observed cache telemetry. At Moonshot's published rates, K3's full-sample CPSC is $44.24 with no
cache, $9.85 at 90%, $7.94 at 95%, $6.79 at the reported 98%, and $6.03 even with every input token
priced as a cache hit.

That last bound matters. Sol high's reported CPSC is $5.00, so no feasible K3 cache fraction makes
K3 the cheaper standalone configuration in this snapshot. The Fable comparison is different:
Fable xhigh's reported CPSC is $19.19, so K3's reported-cost advantage over Fable survives once K3's
cache fraction exceeds roughly two thirds. Four of Fable xhigh's 452 costs are imputed, but the gap
is too large for that small missingness to drive the result.

The economic description is therefore precise: K3 is inexpensive relative to Fable, but not
lightweight and not the standalone cost winner. Its low sticker price depends materially on high
prefix-cache reuse, while its output appetite remains large.

## Retrospective policy frontier

The policy replay is exploratory and selection-conditioned. It exhaustively assigns the four
observed attempts per model to four ordered slots, averages over distinct assignments, and stops
cost and work after the first success. Coverage depends on the model multiset; order affects
stopped cost and work. This is a reconstruction from the same tasks used to select policies, not a
prospective result. Bootstrap intervals resample tasks or repositories while holding each observed
four-attempt multiset fixed; they do not include fresh-rollout Monte Carlo uncertainty.

Across all 256 four-call policies over Grok, Sol high, Fable xhigh, and K3 on the exact 111-task
cohort, K-containing policies appear on the reported-cost frontier:

| Policy | Coverage | Stopped reported cost/task | Stopped CPSC | Trial hours/task |
| --- | ---: | ---: | ---: | ---: |
| `GSGG` | 87.894% | $4.952 | $5.634 | 0.312 |
| `GSGS` | 90.465% | $5.098 | $5.635 | 0.315 |
| `GSGK` | 91.226% | $5.257 | $5.763 | 0.484 |
| `GSKS` | 92.042% | $5.388 | $5.854 | 0.534 |
| `GSKK` | 92.070% | $5.553 | $6.031 | 0.673 |
| `SKSK` | 92.317% | $6.069 | $6.574 | 0.778 |
| `SKSF` | 92.361% | $7.075 | $7.660 | 0.672 |

The role is narrower than “K3 unlocks new capability.” Replacing the last Fable in `GSGF` with
K3 changes coverage by -0.150 points, with repository-bootstrap interval -1.634 to 1.341, while
saving $1.371 per task and adding 0.132 trial-hours. Replacing Sol in `GSGS` with K3 adds 0.760
points, interval -0.982 to 2.579, while adding $0.159 and 0.169 hours per task. Maximum coverage
without K3 is 92.117%; maximum coverage when K3 is admitted to the four-model alphabet is 92.361%,
an unresolved 0.244-point difference.

The full search adds Sol xhigh, Sol max, Terra, and Luna to the alphabet, denoted `X`, `M`, `T`, and
`L`. Across all 4,096 policies on the exact 108-task all-eight cohort, K3 appears in six of thirteen
reported-cost frontier policies, two of sixteen recorded-step frontier policies, and none of the
twelve elapsed-agent-time frontier policies. `LGLK` covers 92.824% at $4.760 per task. Against
`LGLS`, it adds 0.588 points, interval -1.124 to 2.428, and costs $0.097 more. Against `LGLF`, it
loses 0.492 points, interval -1.779 to 0.860, and saves $1.025. All 3,456 attempt rows in this exact
cohort have reported cost values; K3's 98% cache share remains an assumption inside those values.

Neither of the two broad in-sample optima needs K3. The highest-coverage policy at or below the
homogeneous Sol high policy's reported cost is `LGLF`, at 93.316% and $5.785 per task. The overall
coverage maximum is `LMFF`, at 93.721%. Both exclude K3.

K3 does occupy cheaper near-optima. Under the Sol-high budget, `LGKM` gives up 0.127 coverage
points versus `LGLF`, repository-bootstrap interval -1.804 to 1.672, while saving $0.474 per task,
interval $0.181 to $0.801. Near maximum coverage, `LKMF` gives up 0.076 points versus `LMFF`,
interval -1.025 to 0.833, while saving $2.088 per task, interval $1.354 to $2.942. These fixed
pairs were chosen after inspecting the frontier. They describe K3's price tier; they do not validate
the policies.

K3's cost-frontier membership depends on warm-cache economics. Holding behavior and token volumes
fixed, K3 appears in none of the cost-frontier policies at 0% or 50% cache, six at 90% and 98%, and
eight at 100%. `LGLF` remains the best policy under the Sol-high budget through the reported 98%
scenario. This is billing sensitivity, not a behavioral simulation of cold-cache execution.

A repository-held-out selection check does not favor K3. Across 200 grouped five-fold splits,
allowing K3 changes held-out coverage by -0.091 points on average and adds $0.152 per task versus
selecting from the other seven configurations. The split-level 2.5th to 97.5th percentile range for
coverage is -1.971 to 1.741 points. Leave-one-repository-out selection gives -1.515 points and
+$0.313 per task, with a K-containing policy selected for 29 of 88 held-out repositories. These are
partition-sensitivity diagnostics, not confidence intervals or proof that K3 is harmful. They show
no held-out benefit despite K3's in-sample frontier membership.

**Exploratory interpretation:** K3 fills a price-and-coverage gap between cheaper Sol/Luna policies
and expensive Fable policies under DeepSWE's assumed cache accounting. The frozen data do not
establish a capability lift over Sol or Luna, and they do not support presenting any named K3
policy as optimal.

## Harness compatibility is a bounded threat

The public K3 job is identified as direct Moonshot through mini-swe-agent, but its request payload
and accessible trajectory logs are missing. Stock mini-swe-agent 2.4.4 calls LiteLLM's completed
response path without enabling streaming. Kimi's current API defaults `stream` to false but its
benchmark guidance says streaming is mandatory for reliability, warns that non-streaming can
produce mid-connection interruptions, and recommends low concurrency.

This makes non-streaming a plausible implementation-level hypothesis for the ten exact three-hour
caps, not a confirmed property of the unpublished DeepSWE payload. Seven caps occur in the initial
200-launch wave, but the launch-wave association is unresolved. Reclassifying the nine
low-throughput caps as exclusions raises K3 from 68.51% to 69.91%; excluding all ten raises it to
70.07%, and converting all ten to passes gives an upper bound of 70.73%. The operational concern is
real, but it cannot transform the overall capability conclusion.

## External triangulation

These sources are context, not pooled evidence. They use different task sets, effort settings,
harnesses, safety behavior, and providers.

Moonshot's launch table reports K3 at 88.3 on Terminal-Bench 2.1 versus Sol's 88.8, 77.8 on
Program Bench versus Sol's 77.6 and Fable's 76.8, and 42.0 on SWE Marathon versus Sol's 39.0 and
Fable's 35.0. On FrontierSWE, K3's 81.2 sits between Fable's 86.6 and Sol's 71.3. These are
vendor-reported launch results, and the table notes potential Fable fallback and Sol cyberguard
effects. [Kimi K3 launch report](https://www.kimi.com/fr-fr/blog/kimi-k3)

Artificial Analysis provides the cleanest independent model-level cross-check because its Coding
Index evaluates models under one published evaluation framework: two-thirds Terminal-Bench 2.1
and one-third SciCode. The aggregate results are again crowded rather than decisive:

| Configuration | Coding Index | Terminal-Bench 2.1 | SciCode |
| --- | ---: | ---: | ---: |
| Kimi K3 | 76.24 | 85.02% | 58.68% |
| Claude Fable 5 max with Opus 4.8 fallback | 76.49 | 84.64% | 60.19% |
| GPT-5.6 Sol max | 77.39 | 88.02% | 56.13% |

These common-framework aggregate scores corroborate frontier-level coding capability and another
cross-benchmark rank reversal, but Artificial Analysis does not publish the K3 task-level rows or
trajectories needed to test complementarity. The Fable row must retain its fallback label.
[Methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking),
[K3 versus Sol](https://artificialanalysis.ai/models/comparisons/kimi-k3-vs-gpt-5-6-sol), and
[K3 versus Fable](https://artificialanalysis.ai/models/comparisons/kimi-k3-vs-claude-fable-5)

Its broader model evaluation also records 130 million K3 output tokens, versus 70 million for Sol
max and 87 million for Fable with fallback, and reports K3 at 62 output tokens/second. This
corroborates the high-verbosity shape outside DeepSWE, though it does not explain DeepSWE's
wall-time ratios. [K3](https://artificialanalysis.ai/models/kimi-k3),
[Sol max](https://artificialanalysis.ai/models/gpt-5-6-sol), and
[Fable](https://artificialanalysis.ai/models/claude-fable-5)

No second public task-level dataset currently contains K3, Fable, and Sol results under a common
harness. In particular, the [official SWE-bench Multilingual
leaderboard](https://www.swebench.com/multilingual.html) has none of those three rows. Aggregate
benchmark scores can triangulate level and rank instability, but only DeepSWE supports the
task-overlap, retry, and policy analyses in this note.

The closest public task-level sanity check is explicitly predecessor-only. On 300 SWE-bench
Multilingual tasks under mini-SWE-agent 2.0.0a0, Kimi K2.5 solves 202, GPT-5.2 high solves 200, and
Claude 4.5 Sonnet solves 201. Their observed union is 244 tasks, with 13 Kimi-only, 13 GPT-only, and
9 Claude-only solves. Replaying the public per-instance costs makes GPT then Kimi then Claude the
cheapest stop-on-success order at $0.988 per task, versus $1.146 for Claude then Kimi then GPT.
This reproduces the generic complementarity-and-order pattern on another fixed harness, not any
claim about K3, Fable, or Sol. [Kimi rows](https://github.com/SWE-bench/experiments/tree/2f15350cd32becc4569e0d826361048555b605c0/evaluation/multilingual/20260213_mini-v2.0.0a0_kimi-k2-5),
[GPT rows](https://github.com/SWE-bench/experiments/tree/2f15350cd32becc4569e0d826361048555b605c0/evaluation/multilingual/20260213_mini-v2.0.0a0_gpt-5-2-high),
and [Claude rows](https://github.com/SWE-bench/experiments/tree/2f15350cd32becc4569e0d826361048555b605c0/evaluation/multilingual/20260213_mini-v2.0.0a0_claude-4-5-sonnet)

## Existing-data saturation

The material quantitative avenues exposed by the public rows have now been covered: all-configuration
capability and cost rank; exact eight-configuration matched comparisons; retry dependence and
order-neutral solve curves; pairwise, union, and Shapley coverage; task metadata and model-family
difficulty interactions; residual failure geometry; latency, caps, chronology, and error shape;
cache-price sensitivity; exhaustive four-call policies; repository-held-out policy selection;
common-framework external aggregates; and a fixed-harness predecessor task-level check.

The remaining important questions are not additional calculations on these rows. They require data
the artifacts do not contain: actual K3 cache telemetry, request payloads and retry logs, accessible
trajectories, immutable model snapshots or seeds, issue bodies and patches, task dates, richer task
categories, and current-model task-level outcomes from a second common harness. Without those,
mechanism, causal provider effects, production routing, and out-of-sample K3 portfolio value remain
unidentified.

## Research conclusions and boundaries

1. **Derived:** No pairwise pass-rate difference is resolved between K3 and the six other frontier
   peers in the matched basket; only K3's lead over Grok is resolved. K3 distributes successful
   attempts across task identities differently.
2. **Derived:** Same-model retries add coverage with steeply diminishing returns and substantial
   within-task dependence. Four runs are closer to 1.87 independent attempts for mean estimation.
3. **Exploratory:** K3's strongest capability signal is a GPT-family-specific difficulty
   interaction. Its residual task geometry is instead unusually similar to Fable. Neither result
   supports universal superiority on difficult tasks or a stable language specialization.
4. **Derived:** K3 cannot beat Sol high's standalone CPSC at any feasible cache fraction under the
   published K3 prices, reported input/output counters, and hypothetical cache fractions. Its price
   case is against Fable, not Sol.
5. **Observed:** K3 is much slower than Sol and Fable in this run, even after removing the nine
   obvious low-throughput caps. The ten caps are operational evidence, not a complete explanation.
6. **Exploratory:** K3 occupies a narrow in-sample policy niche as a cheaper Fable substitute, but
   repository-held-out policy selection does not benefit from admitting K3.
7. **Unresolved:** Outcome artifacts cannot separate model behavior, provider behavior, run date,
   concurrency, harness behavior, or task environment. Those mechanism claims cannot be made from
   the available evidence.

**Paper gate: hold.** The original paper should remain unchanged. The K3 findings are useful as a
dated external reanalysis, but the strongest positive interactions and policies are exploratory,
the cost result depends on assumed cache accounting, and the held-out policy diagnostics show no
benefit from admitting K3.

All intervals and tests are exploratory unless explicitly described otherwise. Repository
clustering addresses shared repositories but not benchmark selection, training-data overlap,
provider drift, or generalization to future tasks.
