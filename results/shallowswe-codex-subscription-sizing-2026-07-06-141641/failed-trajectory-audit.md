# Failed Trajectory Audit

Failed trajectories audited: 53
Unique failed tasks: 18

## Stage Counts

- `diagnostic_gpt55_high`: 6
- `diagnostic_gpt55_xhigh`: 6
- `fixed_ceiling_gpt55_medium`: 8
- `floor_gpt54mini_low`: 33

## Task Verifier Sanity

- `audit-log-normalization`: pass; solution=1
- `billing-revenue-rollup`: pass; solution=1
- `config-key-rollover`: pass; solution=1
- `customer-health-dashboard-screen`: pass; solution=1
- `deployment-approval-reconcile`: pass; solution=1
- `feature-branch-select-commits`: pass; solution=1
- `feature-entitlements-admin-screen`: pass; solution=1
- `incident-comms-pipeline`: pass; solution=1
- `invoice-multi-source-merge`: pass; solution=1
- `ledger-schema-upgrade`: pass; solution=1
- `markdown-table-inventory`: pass; solution=1
- `release-branch-cherry-pick`: pass; solution=1
- `release-train-reconcile`: pass; solution=1
- `renewal-risk-admin-screen`: pass; solution=1
- `strip-sort-allowlist`: pass; solution=1
- `subscription-summary-report`: pass; solution=1
- `ticket-state-reconcile`: pass; solution=1
- `ticket-update-dont-duplicate`: pass; solution=1

## Failed Trajectories

- `diagnostic_gpt55_high` `audit-log-normalization` `audit-log-normalization__GxGDFfJ`: AssertionError: missing /app/output/summary.json
- `diagnostic_gpt55_high` `feature-branch-select-commits` `feature-branch-select-commits__HFBm7dt`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `diagnostic_gpt55_high` `incident-comms-pipeline` `incident-comms-pipeline__XiHaK6z`: AssertionError: Lists differ: [{'action': 'component_status', 'detail': [214 chars]pi'}] != []
- `diagnostic_gpt55_high` `markdown-table-inventory` `markdown-table-inventory__SBcx9MB`: AssertionError
- `diagnostic_gpt55_high` `release-branch-cherry-pick` `release-branch-cherry-pick__xV9y2cP`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmpqlmxki91/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `diagnostic_gpt55_high` `subscription-summary-report` `subscription-summary-report__3qTaXFP`: AssertionError
- `diagnostic_gpt55_xhigh` `audit-log-normalization` `audit-log-normalization__TfXyNRk`: AssertionError: missing /app/output/summary.json
- `diagnostic_gpt55_xhigh` `feature-branch-select-commits` `feature-branch-select-commits__iE27hme`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `diagnostic_gpt55_xhigh` `incident-comms-pipeline` `incident-comms-pipeline__uoDfEQy`: AssertionError: Lists differ: [{'action': 'component_status', 'detail': [122 chars]pi'}] != []
- `diagnostic_gpt55_xhigh` `markdown-table-inventory` `markdown-table-inventory__aFDptw7`: AssertionError
- `diagnostic_gpt55_xhigh` `release-branch-cherry-pick` `release-branch-cherry-pick__6GqwR4J`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmp7q98nk7l/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `diagnostic_gpt55_xhigh` `subscription-summary-report` `subscription-summary-report__xdU7ifR`: AssertionError
- `fixed_ceiling_gpt55_medium` `audit-log-normalization` `audit-log-normalization__RXcY5tX`: AssertionError: missing /app/output/summary.json
- `fixed_ceiling_gpt55_medium` `customer-health-dashboard-screen` `customer-health-dashboard-screen__zV5STBd`: AssertionError: defaultdict(<class 'str'>, {'accounts': '[100 chars]d2'}) != {'accounts': '4', 'high-risk': '1', 'open[31 chars] '2'}
- `fixed_ceiling_gpt55_medium` `deployment-approval-reconcile` `deployment-approval-reconcile__fJzvcgi`: AssertionError: {'call_log': [{'action': 'deploy', 'detail'[871 chars]'}}}} != {'services': {'search': {'rings': {'canary'[837 chars]'}}]}
- `fixed_ceiling_gpt55_medium` `feature-branch-select-commits` `feature-branch-select-commits__7yrNqhs`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `fixed_ceiling_gpt55_medium` `incident-comms-pipeline` `incident-comms-pipeline__GjL5f2R`: AssertionError: Lists differ: [{'action': 'component_status', 'detail': [122 chars]pi'}] != []
- `fixed_ceiling_gpt55_medium` `markdown-table-inventory` `markdown-table-inventory__rm2MDyU`: AssertionError
- `fixed_ceiling_gpt55_medium` `release-branch-cherry-pick` `release-branch-cherry-pick__DWw6bWS`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmp8ntf52_o/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `fixed_ceiling_gpt55_medium` `subscription-summary-report` `subscription-summary-report__ZztDQ59`: AssertionError
- `floor_gpt54mini_low` `audit-log-normalization` `audit-log-normalization__8Zpi5Sh`: AssertionError: missing /app/output/summary.json
- `floor_gpt54mini_low` `audit-log-normalization` `audit-log-normalization__NTAqYEZ`: AssertionError
- `floor_gpt54mini_low` `audit-log-normalization` `audit-log-normalization__QLGMLp6`: AssertionError
- `floor_gpt54mini_low` `billing-revenue-rollup` `billing-revenue-rollup__2vzkSaV`: AssertionError
- `floor_gpt54mini_low` `config-key-rollover` `config-key-rollover__LeieyST`: AssertionError: 'DISPATCH_VISIBILITY=all' not found in 'DISPATCH_REGION=west\nDISPATCH_ACCOUNT=acme\nDISPATCH_INCLUDE_CLOSED=1\n'
- `floor_gpt54mini_low` `customer-health-dashboard-screen` `customer-health-dashboard-screen__jmrsdVq`: AssertionError: defaultdict(<class 'str'>, {'accounts': '[100 chars]d2'}) != {'accounts': '4', 'high-risk': '1', 'open[31 chars] '2'}
- `floor_gpt54mini_low` `feature-branch-select-commits` `feature-branch-select-commits__PAzikdN`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `floor_gpt54mini_low` `feature-branch-select-commits` `feature-branch-select-commits__hNdY3Nm`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `floor_gpt54mini_low` `feature-branch-select-commits` `feature-branch-select-commits__kV8ES7i`: FileNotFoundError: [Errno 2] No such file or directory: '/app/selected_commits.txt'
- `floor_gpt54mini_low` `feature-entitlements-admin-screen` `feature-entitlements-admin-scree__2tmW4xd`: AssertionError: defaultdict(<class 'str'>, {'workspaces':[108 chars]g1'}) != {'workspaces': '3', 'blocked': '7', 'over[35 chars] '1'}
- `floor_gpt54mini_low` `incident-comms-pipeline` `incident-comms-pipeline__Dcqbu5T`: AssertionError: {'_reconciled_timeline': '791f285dfb69062ca[3456 chars]m'}}} != {'components': {'api': 'operational', 'web'[3364 chars] 102}
- `floor_gpt54mini_low` `incident-comms-pipeline` `incident-comms-pipeline__Ns6bUXd`: AssertionError: {'_reconciled_timeline_signature': '{"event[4827 chars]m'}}} != {'components': {'api': 'operational', 'web'[3364 chars] 102}
- `floor_gpt54mini_low` `invoice-multi-source-merge` `invoice-multi-source-merge__TVT9voR`: AssertionError: Lists differ: [{'in[786 chars] '20260601', 'updated_at': '20260607', 'source': 'legacy'}] != [{'in[786 chars] '2026-06-01', 'updated_at': '2026-06-07', 'source': 'legacy'}]
- `floor_gpt54mini_low` `invoice-multi-source-merge` `invoice-multi-source-merge__qhbCvoh`: AssertionError: Lists differ: [{'source': 'legacy', 'row_ref': '3', 'invoice_id': 'I[212 chars]id'}] != [{'source': 'api', 'row_ref': '3', 'invoice_id': '', '[212 chars]nt'}]
- `floor_gpt54mini_low` `ledger-schema-upgrade` `ledger-schema-upgrade__VZ9FBvP`: AssertionError: {'adjustment_cents': 5, 'adjustment_events'[114 chars]': 4} != {'usage_events': 4, 'adjustment_events': 2,[115 chars]: 50}
- `floor_gpt54mini_low` `markdown-table-inventory` `markdown-table-inventory__XLQEvaz`: AssertionError
- `floor_gpt54mini_low` `markdown-table-inventory` `markdown-table-inventory__qMEQPbX`: AssertionError
- `floor_gpt54mini_low` `markdown-table-inventory` `markdown-table-inventory__tKm6i3x`: AssertionError
- `floor_gpt54mini_low` `release-branch-cherry-pick` `release-branch-cherry-pick__AKW244m`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmp4qg14xhp/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `release-branch-cherry-pick` `release-branch-cherry-pick__JTagL7G`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmp5vr4v796/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `release-branch-cherry-pick` `release-branch-cherry-pick__nAcDga8`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmpt7qdfowh/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `release-train-reconcile` `release-train-reconcile__Q56uUJQ`: AssertionError: 3 not less than 2
- `floor_gpt54mini_low` `renewal-risk-admin-screen` `renewal-risk-admin-screen__6mUbSXT`: AssertionError: 'renewal_soon,open_critical_ticket' != 'renewal_soon,open_critical_ticket,stale_usage'
- `floor_gpt54mini_low` `strip-sort-allowlist` `strip-sort-allowlist__F34Ksbx`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmppzagwzao/app/scripts/build_outputs.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `subscription-summary-report` `subscription-summary-report__5ieuqhL`: AssertionError
- `floor_gpt54mini_low` `subscription-summary-report` `subscription-summary-report__azHyo6H`: AssertionError
- `floor_gpt54mini_low` `subscription-summary-report` `subscription-summary-report__yTbbBwz`: AssertionError
- `floor_gpt54mini_low` `ticket-state-reconcile` `ticket-state-reconcile__4BX9Sow`: AssertionError: ('retry', 'TKT-100', ' Billing.Retry ') not found in [('dedupe', 'TKT-101', ' Billing.Retry '), ('retry', '', ' Billing.Retry '), ('update', 'TKT-100', ' Billing.Retry '), ('reopen', 'TKT-100', ' Billing.Retry '), ('update', 'TKT-103', 'ops.rotate-secret'), ('retry', '', 'ops.rotate-secret'), ('close', 'TKT-103', 'ops.rotate-secret'), ('create', 'TKT-105', 'support.new-sla')]
- `floor_gpt54mini_low` `ticket-state-reconcile` `ticket-state-reconcile__MTs8v8M`: AssertionError: ('retry', 'TKT-100', ' Billing.Retry ') not found in [('dedupe', 'TKT-101', ' Billing.Retry '), ('retry', 'TKT-100', ''), ('update', 'TKT-100', ' Billing.Retry '), ('reopen', 'TKT-100', ' Billing.Retry '), ('update', 'TKT-103', 'ops.rotate-secret'), ('retry', 'TKT-103', ''), ('close', 'TKT-103', 'ops.rotate-secret'), ('noop', 'TKT-103', 'ops.rotate-secret'), ('create', 'TKT-105', 'support.new-sla')]
- `floor_gpt54mini_low` `ticket-state-reconcile` `ticket-state-reconcile__ir9pAqS`: AssertionError: ('dedupe', 'TKT-101', ' Billing.Retry ') not found in [('dedupe', 'TKT-101', 'BILLING.RETRY'), ('retry', 'TKT-100', 'billing.retry'), ('update', 'TKT-100', ' Billing.Retry '), ('reopen', 'TKT-100', ' Billing.Retry '), ('update', 'TKT-103', 'ops.rotate-secret'), ('retry', 'TKT-103', 'ops.rotate-secret'), ('close', 'TKT-103', 'ops.rotate-secret'), ('create', 'TKT-105', 'support.new-sla')]
- `floor_gpt54mini_low` `ticket-update-dont-duplicate` `ticket-update-dont-duplicate__BEiTvqr`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmpnbl9g1hq/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `ticket-update-dont-duplicate` `ticket-update-dont-duplicate__aY6Qsfk`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmp7cu27ny7/app/scripts/apply_task.py']' returned non-zero exit status 1.
- `floor_gpt54mini_low` `ticket-update-dont-duplicate` `ticket-update-dont-duplicate__rwh7fbj`: subprocess.CalledProcessError: Command '['/usr/local/bin/python3', '/tmp/tmpbs534rjc/app/scripts/apply_task.py']' returned non-zero exit status 1.
