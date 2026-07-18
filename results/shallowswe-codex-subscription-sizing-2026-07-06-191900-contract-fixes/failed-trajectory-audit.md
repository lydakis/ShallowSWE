# Failed Trajectory Audit

Failed trajectories audited: 3
Unique failed tasks: 3

## Stage Counts

- `floor_gpt54mini_low`: 3

## Task Verifier Sanity

- `audit-log-normalization`: pass; solution=1
- `billing-revenue-rollup`: pass; solution=1
- `feature-branch-select-commits`: pass; solution=1

## Failed Trajectories

- `floor_gpt54mini_low` `audit-log-normalization` `audit-log-normalization__VGKwEqb`: AssertionError
- `floor_gpt54mini_low` `billing-revenue-rollup` `billing-revenue-rollup__ffJ6hko`: AssertionError
- `floor_gpt54mini_low` `feature-branch-select-commits` `feature-branch-select-commits__mzF7hDP`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
