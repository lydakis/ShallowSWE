# Fable review: cross-family framing

Command:

```text
claude -c -p --model fable --effort high --tools Read --permission-mode dontAsk
```

The objection is half right, and the generated tables contain a result stronger than anything
currently in the paper. The fix is not merely to give the other configurations more airtime.

## What the full panel shows

1. All 13 configurations on the pass-rate/mean-attempt-cost Pareto frontier are GPT-5.6 Luna,
   Terra, or Sol effort settings. Cross-provider interpretation must remain descriptive because
   price semantics are not harmonized. Within the OpenAI route, every GPT-5.4 and GPT-5.5 effort
   level is strictly dominated by a GPT-5.6 Sol setting at a corresponding effort level.
2. Sol max is statistically unresolved on paired solve-rate difference against Sol high, Sol
   xhigh, Terra max, and Luna max, while being resolved-more-expensive than all four in every one
   of 10,000 task-bootstrap replicates. This is a broader result than a single Luna/Sol pair.
3. Luna max and Sol high are unresolved on both solve rate and CPSC. Much of the apparent Luna
   advantage over Sol max is therefore an effort-setting result: reducing Sol from max to high
   recovers most of the cost gap without changing the base model.
4. Luna low solves only 1.5% of attempts yet has realized CPSC of $4.68, slightly above Luna max's
   $4.51 at 67.2% pass rate. Its reliability-tax share is 98.6%. This is a direct illustration
   that unconstrained realized CPSC is not a decision rule.

## Recommended hierarchy

1. Lead with a 41-configuration pass-rate versus mean-attempt-cost frontier.
2. Add a table comparing Sol max with its four statistically unresolved, decisively cheaper
   alternatives.
3. Retain the Luna max/Sol max robustness analysis as the widest-gap exemplar, while noting that
   Sol high/Sol max is the cleaner effort-only contrast and Luna max/Sol high is unresolved.
4. Open policy dependence with Luna low and frame the reliability floors as navigation through a
   broader configuration menu.
5. Demote the panel-dependent rank-correlation figure and move the Sol-anchored pseudo-budget table
   to the appendix.

## Cautions

- Do not call the top configurations equivalent or tied. Their solve-rate differences are
  statistically unresolved with four attempts per task; that is not an equivalence test.
- Cross-provider dollar comparisons remain soft. The other model families should be shown and
  discussed descriptively, while the strongest comparative claims stay within provider routes.

The resulting thesis is that trial-level economics reveals an economically ordered set near the
top of the capability leaderboard, while reported-price comparisons across provider routes remain
descriptive.
