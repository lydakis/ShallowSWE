# Fable review: neutral DeepSWE economic read

Command:

```text
claude -p --model fable --effort high --tools Read --permission-mode dontAsk
```

Fable read the executed insight-audit notebook, the generated tables, the frozen preanalysis
document, and the machine-readable plan. It was instructed not to read the paper or prior reviews.

## Empirical read

- The data reconcile cleanly: 18,396 scored attempts, 41 configurations, 13 model families, and
  113 tasks. There are 126 excluded infrastructure rows and 21 imputed costs.
- In the fixed 13-family view, capability and reported-dollar economic ranks differ. Sol max is
  first on pass rate and seventh on CPSC; Fable xhigh is second and ninth; Luna max is fourth and
  first. The low end of the 41-configuration CPSC table is entirely GPT-5.6.
- Higher effort generally purchases more solve rate at higher CPSC. Luna and Terra are the only
  families with interior CPSC minima, caused by very weak low-effort settings. Only Luna low to
  medium has a paired interval resolving both higher pass rate and lower CPSC, and both endpoints
  remain low-reliability configurations.
- Failed and successful attempts have similar conditional spend. Their ratio ranges from 0.72 to
  1.23 with median 1.02. The reliability-tax share therefore correlates 0.995 with failure rate.
- Every reliability-floor winner and failure-price-sensitivity winner is a GPT-5.6 configuration.
  This is narrow to one provider generation and cannot be interpreted as provider-independent
  model efficiency without common-price reconciliation.

## Arithmetic versus trial-level information

Realized CPSC is mean attempt cost divided by pass rate to machine precision. Full-suite CPSC,
economic ranks, and their Pareto frontier are therefore recoverable from the published aggregates.
The tax share is also almost a restatement of failure rate on this benchmark.

Trial-level data are required for the empirical similarity between failed and successful attempt
spend, paired task-bootstrap uncertainty, task-difficulty strata, exclusion sensitivities,
reliability-policy reselection, task-level pseudo-budgets, and correction of the small denominator
mismatch created by missing-cost rows.

## Robust and weakened observations

- Seven configurations have paired solve-rate differences from Sol max whose 95% task-bootstrap
  intervals contain zero: Luna max, Sol high, Sol xhigh, Terra max, and Fable high, xhigh, and max.
  The four OpenAI alternatives cost 0.39 to 0.62 times Sol max per success and are cheaper in all
  10,000 replicates. The three Fable alternatives cost 1.16 to 2.69 times Sol max and are more
  expensive in at least 9,884 replicates.
- Exact reliability-floor winner identity becomes unstable at high floors. At 0.70 the point
  winner is reselected in 16% of replicates; at 0.75, 67% of replicates have no eligible model.
- Counting infrastructure exclusions as failures lowers several Claude-route pass rates but leaves
  the qualitative provider-route frontier structure unchanged.
- On the 17 post-hoc rare tasks, Luna max and Fable max have nearly identical point solve rates,
  36.8% and 36.9%, while their realized CPSC values are $11.07 and $68.76. This weakens the specific
  claim that the cheap GPT-5.6 configurations win only by solving easy tasks.

## Editorial conclusion

Fable judged that a short descriptive paper is coherent if it includes the negative result that
the failure-spend decomposition is nearly degenerate on DeepSWE and focuses the trial-level
contribution on resolved cost separation under unresolved capability separation. It recommended
adding the frozen token-per-success and step-per-success estimands before circulation, because the
reported-dollar separation may be a pricing result rather than a resource-efficiency result.
