Build a privacy data-retention evidence package from the synthetic repository.

Run shape:

```sh
python scripts/build_retention_audit.py --root <repo-root> --output <output-dir>
```

If no arguments are provided, use `/app` as the root and `/app/output` as the output directory.
Create the `scripts/` directory if it does not exist.

Inputs:

- `catalog/systems.json`: array of system objects with `system_id`, `owner_team`, and `tier`.
- `catalog/datasets.csv`:
  `dataset_id,system_id,owner_team,classification,subject_type,retention_days,deletion_mode,storage_path`.
- `policies/retention_policy.json` with:
  - `report_date`;
  - `classification_retention_days`;
  - `stale_job_days`;
  - `export_job_stale_days`;
  - `propagation_required_classifications`;
  - `due_days`;
  - `action_order`.
- `jobs/purge_jobs.csv`: `job_id,dataset_id,mode,schedule_days,last_success_at,filter_expr`.
- `jobs/export_jobs.csv`: `job_id,dataset_id,last_success_at,scope`.
- `legal/holds.csv`: `hold_id,dataset_id,status,expires_on,reason`.
- `lineage/downstream_edges.csv`:
  `source_dataset_id,target_dataset_id,delete_propagates,export_propagates`.
- `incidents/data_incidents.csv`: `dataset_id,severity,status,opened_at`.
- `exemptions/retention_exemptions.csv`: `dataset_id,control,expires_on,reason`.
- Source files under `services/<system_id>/src/**`.

Rules:

- Dates use `YYYY-MM-DD`. A job is current when `report_date - last_success_at <= stale window`.
- `expected_retention_days` is the policy limit for the dataset classification.
- `configured_retention_days` is the dataset row's `retention_days`.
- Active exemptions have `expires_on >= report_date`; expired exemptions do nothing.
- Active legal holds have `status == active` and `expires_on >= report_date`.
- Source evidence files are sorted relative paths under the repo root whose text contains the
  exact `dataset_id`.
- Missing controls are computed in this order, after active exemptions remove matching controls:
  - `retention_limit`: configured retention exceeds expected retention;
  - `purge_job`: `deletion_mode != none` and there is no purge job for the dataset with matching
    `mode`;
  - `purge_job_current`: there is a matching purge job, but no matching purge job is both current
    and scheduled with `schedule_days <= expected_retention_days`;
  - `subject_export`: `subject_type` is `customer` or `prospect`, and there is no current export
    job for the dataset with `scope == subject`;
  - `downstream_delete`: classification is in `propagation_required_classifications`, and at least
    one downstream edge has `delete_propagates == false`;
  - `downstream_export`: `subject_type` is `customer` or `prospect`, and at least one downstream
    edge has `export_propagates == false`;
  - `source_reference`: no source evidence file mentions the dataset id;
  - `open_incident`: at least one incident for the dataset has `status == open`.
- `downstream_delete_gaps` and `downstream_export_gaps` list target dataset ids sorted
  alphabetically. Active exemptions remove the corresponding missing control but do not remove the
  gap evidence.
- Dataset status:
  - `blocked` if any missing control is one of `retention_limit`, `purge_job`,
    `downstream_delete`, or `open_incident`;
  - `needs_work` if any other missing control remains;
  - `accepted_risk` if no missing controls remain but there is an active legal hold;
  - `ready` otherwise.

Output files:

- `dataset_retention.json`
- `owner_gaps.csv`
- `purge_plan.csv`
- `summary.json`

`dataset_retention.json` has exactly one top-level key, `datasets`, containing rows sorted by
`dataset_id`. Each row has exactly these keys:

- `dataset_id`
- `system_id`
- `owner_team`
- `classification`
- `subject_type`
- `expected_retention_days`
- `configured_retention_days`
- `deletion_mode`
- `status`
- `missing_controls`
- `exempted_controls`
- `legal_hold_active`
- `downstream_delete_gaps`
- `downstream_export_gaps`
- `source_evidence_files`
- `purge_jobs`
- `export_jobs`
- `open_incidents`

`purge_jobs` and `export_jobs` list matching job ids sorted alphabetically. `open_incidents` is an
integer count.

`owner_gaps.csv` columns are exactly
`owner_team,datasets,blocked,needs_work,accepted_risk,ready,missing_controls,downstream_gaps,open_incidents,legal_holds`,
sorted by `owner_team`.

- `missing_controls` sums the length of each owned dataset's `missing_controls`.
- `downstream_gaps` sums downstream delete and export gap counts.
- `legal_holds` counts datasets with active legal holds.

`purge_plan.csv` columns are exactly
`dataset_id,owner_team,priority,due_date,actions,evidence`, sorted by priority (`P0`, `P1`, `P2`,
`P3`) and then `dataset_id`. Include every dataset whose status is not `ready`.

- Priority is `P0` for `blocked`, `P1` for `needs_work` with `retention_limit`,
  `downstream_delete`, or `open_incident`, `P2` for other `needs_work`, and `P3` for
  `accepted_risk`.
- `due_date` is `report_date + due_days[status]`.
- `actions` is a semicolon-separated list following `action_order`. Use this mapping:
  - `retention_limit`: `reduce retention to policy limit`
  - `purge_job`: `add purge job for deletion mode`
  - `purge_job_current`: `repair stale or slow purge job`
  - `subject_export`: `repair subject export job`
  - `downstream_delete`: `propagate deletion to downstream datasets`
  - `downstream_export`: `propagate export to downstream datasets`
  - `source_reference`: `add source dataset annotation`
  - `open_incident`: `resolve open data incident`
  - `legal_hold`: `review active legal hold`
- Include the `legal_hold` action after missing-control actions when `legal_hold_active` is true.
- `evidence` is a semicolon-separated list: source evidence files, then `purge:<job_id>`, then
  `export:<job_id>`, then `hold:<hold_id>`, then `incident:<severity>`, each group sorted.

`summary.json` has exactly these keys:

- `datasets`
- `owners`
- `blocked`
- `needs_work`
- `accepted_risk`
- `ready`
- `missing_controls`
- `downstream_delete_gaps`
- `downstream_export_gaps`
- `open_incidents`
- `legal_holds`

All outputs must be deterministic and overwritten on rerun.
