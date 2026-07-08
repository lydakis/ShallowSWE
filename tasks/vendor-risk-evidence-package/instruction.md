Build a vendor-risk evidence package from the synthetic repository.

Run shape:

```sh
python scripts/build_vendor_risk.py --root <repo-root> --output <output-dir>
```

If no arguments are provided, use `/app` as the root and `/app/output` as the output directory.
Create the `scripts/` directory if it does not exist.

Inputs:

- `policies/vendor_risk_policy.json` with `report_date`, `renewal_window_days`,
  `required_evidence_by_criticality`, `dpa_required_data_classes`, `regional_review_regions`,
  `regional_review_data_classes`, `due_days`, and `action_order`.
- `inventory/vendors.csv`:
  `vendor_id,owner_team,criticality,data_classification,renewal_date,status,contract_id`.
- `inventory/services.json`: array of service objects with `service_id`, `vendor_id`,
  `owner_team`, `production`, and `data_types`.
- `contracts/contracts.csv`:
  `contract_id,vendor_id,dpa_signed,subprocessor_notice_days,termination_days`.
- `security/evidence.csv`:
  `vendor_id,evidence_type,status,issued_on,expires_on`.
- `subprocessors/subprocessors.csv`:
  `vendor_id,subprocessor_id,region,approved,data_classification`.
- `incidents/vendor_incidents.csv`: `vendor_id,severity,status,opened_at`.
- `exceptions/risk_exceptions.csv`: `vendor_id,control,expires_on,reason`.
- Source files under `integrations/<vendor_id>/src/**`.

Rules:

- Dates use `YYYY-MM-DD`.
- A security evidence row is current when `status == current` and `expires_on >= report_date`.
- Active exceptions have `expires_on >= report_date`. Active exceptions remove matching missing
  controls but remain listed in `exempted_controls`.
- Source evidence files are sorted relative paths under the repo root whose text contains the exact
  `vendor_id`. Ignore paths containing `/generated/`.
- A renewal is due when `0 <= renewal_date - report_date <= renewal_window_days`.
- Missing controls are computed in this order, after active exceptions remove matching controls:
  - `dpa`: `data_classification` is in `dpa_required_data_classes`, and the linked contract does
    not have `dpa_signed == true`;
  - `soc2_current`: the vendor criticality requires `soc2`, and there is no current `soc2`
    evidence row;
  - `pentest_current`: the vendor criticality requires `pentest`, and there is no current
    `pentest` evidence row;
  - `subprocessor_approval`: at least one subprocessor has `approved == false`;
  - `regional_review`: at least one subprocessor has `region` in `regional_review_regions` and
    `data_classification` in `regional_review_data_classes`;
  - `production_source_reference`: at least one service for the vendor has `production == true`,
    and no non-generated source file mentions the vendor id;
  - `open_incident`: at least one incident for the vendor has `status == open`;
  - `renewal_review`: the renewal is due.
- `subprocessor_gaps` lists unapproved subprocessor ids sorted alphabetically.
- `regional_gaps` lists high-risk region subprocessor ids sorted alphabetically. Active exceptions
  remove the corresponding missing control but do not remove the gap evidence.
- Vendor risk status:
  - `blocked` if any missing control is one of `dpa`, `subprocessor_approval`, or
    `open_incident`;
  - `needs_work` if any other missing control remains;
  - `accepted_risk` if no missing controls remain but `exempted_controls` is non-empty;
  - `ready` otherwise.

Output files:

- `vendor_risk.json`
- `owner_gaps.csv`
- `renewal_actions.csv`
- `summary.json`

`vendor_risk.json` has exactly one top-level key, `vendors`, containing rows sorted by
`vendor_id`. Each row has exactly these keys:

- `vendor_id`
- `owner_team`
- `criticality`
- `data_classification`
- `renewal_date`
- `risk_status`
- `missing_controls`
- `exempted_controls`
- `contract_id`
- `services`
- `source_evidence_files`
- `current_evidence`
- `stale_or_missing_evidence`
- `subprocessor_gaps`
- `regional_gaps`
- `open_incidents`
- `active_exceptions`

`services`, `source_evidence_files`, `current_evidence`, `stale_or_missing_evidence`,
`subprocessor_gaps`, `regional_gaps`, and `active_exceptions` are sorted lists. `open_incidents` is
an integer count.

`owner_gaps.csv` columns are exactly
`owner_team,vendors,blocked,needs_work,accepted_risk,ready,missing_controls,subprocessor_gaps,regional_gaps,open_incidents,renewals_due`,
sorted by `owner_team`.

- `missing_controls` sums the length of each owned vendor's `missing_controls`.
- `subprocessor_gaps` sums unapproved subprocessor gap counts.
- `regional_gaps` sums regional gap counts.
- `open_incidents` sums open incident counts.
- `renewals_due` counts owned vendors with `renewal_review` in either `missing_controls` or
  `exempted_controls`.

`renewal_actions.csv` columns are exactly
`vendor_id,owner_team,priority,due_date,actions,evidence`, sorted by priority (`P0`, `P1`, `P2`,
`P3`), then `renewal_date`, then `vendor_id`. Include every vendor whose status is not `ready`.

- Priority is `P0` for `blocked`, `P1` for `needs_work` with `open_incident`, `P2` for other
  `needs_work`, and `P3` for `accepted_risk`.
- `due_date` is `report_date + due_days[risk_status]`.
- `actions` is a semicolon-separated list following `action_order`. Use this mapping:
  - `dpa`: `execute missing data protection addendum`
  - `soc2_current`: `collect current SOC 2 evidence`
  - `pentest_current`: `collect current penetration test`
  - `subprocessor_approval`: `approve or remove unapproved subprocessors`
  - `regional_review`: `review high-risk processing region`
  - `production_source_reference`: `add production integration source annotation`
  - `open_incident`: `close open vendor incident`
  - `renewal_review`: `complete renewal risk review`
  - `accepted_exception`: `review active risk exception`
- Include the `accepted_exception` action after missing-control actions when `exempted_controls` is
  non-empty.
- `evidence` is a semicolon-separated list: source evidence files, then `service:<service_id>`,
  then `contract:<contract_id>`, then `evidence:<evidence_type>`, then
  `subprocessor:<subprocessor_id>`, then `incident:<severity>`, then `exception:<control>`, each
  group sorted.

`summary.json` has exactly these keys:

- `vendors`
- `owners`
- `blocked`
- `needs_work`
- `accepted_risk`
- `ready`
- `missing_controls`
- `subprocessor_gaps`
- `regional_gaps`
- `open_incidents`
- `renewals_due`
- `active_exceptions`

All outputs must be deterministic and overwritten on rerun.
