The local release train command needs to reconcile a target release plan against deterministic
release-management state.

Run shape:

```sh
python -m release_train.cli \
  --plan <release_plan.json> \
  --state <state.json> \
  --output-state <output.json> \
  --audit-log <audit.jsonl>
```

Inputs:

- `release_plan.json`: desired release plan.
- `state.json`: local deterministic release API state.

Plan fields:

- `release_branch`: branch to reconcile.
- `source_branch`: branch that contains eligible release commits.
- `release_tag`: tag to create for the release.
- `required_checks`: ordered list of check names that must pass for every required commit.
- `required_commits`: ordered list of objects with `sha`, `title`, and `changelog`.
- `blocked_commits`: commits that must not be added to the release branch.
- `changelog_heading`: heading that must exist in the release branch changelog.
- `promotion_rings`: ordered list of promotion objects. Each promotion object has:
  - `ring`: ring name.
  - `required_checks`: ordered list of checks that must pass on the final release head before that
    ring can be marked ready.
  - `approvers`: ordered list of approver handles.
  - `manifest_note`: note to copy into the promotion record.

State fields:

- `branches`: object keyed by branch name. Each value has `head` and `commits`.
- `tags`: object keyed by tag name. Each value is the target commit.
- `status_checks`: object keyed by commit SHA, then check name, with values such as `passed`,
  `pending`, or `failed`.
- `changelog`: object keyed by branch name. Each value is an ordered list of changelog lines.
- `release_manifests`: object keyed by release tag.
- `promotion_records`: object keyed by release tag. Each value is an ordered list of promotion
  records.
- `call_log`: array maintained by the local API.

Rules:

- Reconcile only `release_branch`; leave all other branches unchanged.
- A required commit may be added only if it appears on `source_branch`.
- Add missing required commits to `release_branch` in `required_commits` order.
- Preserve existing commits already on `release_branch`.
- Do not add any commit from `blocked_commits`.
- Do not duplicate commits that are already on `release_branch`.
- The release branch `head` is the last commit in its final `commits` list.
- Every `required_checks` check for every required commit must be `passed` before any promotion
  check, manifest, promotion record, or release tag is written.
- If a required commit check is missing, `pending`, or `failed`, run that check through the local
  API. Running a check marks it `passed`.
- Run missing or non-passing commit checks in required commit order, then check-name order.
- The changelog must contain `changelog_heading` and every required commit's `changelog` line.
- Add missing changelog lines under `changelog_heading`, preserving their `required_commits` order.
- Preserve existing changelog lines and do not duplicate existing required changelog lines.
- Update the changelog before writing the release manifest.
- For every promotion ring, every ring `required_checks` check must be `passed` on the final
  release head before the manifest is written.
- Run missing or non-passing promotion checks in `promotion_rings` order, then check-name order.
- The release manifest is stored at `state["release_manifests"][release_tag]` and must have exactly
  these keys and values:
  - `release_branch`: the plan `release_branch`.
  - `source_branch`: the plan `source_branch`.
  - `target`: the final head of `release_branch`.
  - `required_commits`: the ordered list of required commit SHAs.
  - `blocked_commits`: the ordered plan `blocked_commits` list.
  - `required_checks`: the ordered plan `required_checks` list.
  - `promotion_rings`: the ordered list of promotion ring names.
  - `changelog_heading`: the plan `changelog_heading`.
- After writing the manifest, record one promotion record for each ring in order at
  `state["promotion_records"][release_tag]`.
- A promotion record must have exactly these keys:
  - `ring`: the ring name.
  - `target`: the final release head.
  - `status`: the string `ready`.
  - `approvers`: the ring `approvers` list, preserving order.
  - `note`: the ring `manifest_note`.
- Do not duplicate promotion records for the same `ring`. If a stale record exists for a ring,
  replace that ring's record with the current record.
- Create `release_tag` after all required commits are present, all required commit checks pass, all
  promotion checks pass, the changelog is updated, the manifest is written, and promotion records
  are recorded.
- The release tag target is the final head of `release_branch`.
- If the release is already reconciled, make no state changes and write one `noop` audit row.
- Do not call destructive API operations. Forbidden operations are `delete_branch`, `delete_tag`,
  `force_update_branch`, and `reset_branch`.

The audit log is JSONL. Write one object per logical action with exactly these keys:

- `action`
- `target`
- `detail`

`detail` must be a non-empty string. Do not write an object, array, number, boolean, or null value
for `detail`.

Allowed `action` values:

- `apply_commit`
- `run_check`
- `update_changelog`
- `write_manifest`
- `record_promotion`
- `create_tag`
- `noop`

`target` values are part of the output contract:

- `apply_commit`: the commit SHA.
- `run_check`: `<commit-sha>:<check-name>`.
- `update_changelog`: the release branch name.
- `write_manifest`: the release tag name.
- `record_promotion`: `<release-tag>:<ring>`.
- `create_tag`: the release tag name.
- `noop`: the release tag name.

Ordering is part of the contract: all `apply_commit` rows precede all `run_check` rows, all
`run_check` rows precede `update_changelog`, `update_changelog` precedes `write_manifest`,
`write_manifest` precedes all `record_promotion` rows, and all `record_promotion` rows precede
`create_tag`. `noop` is used only when the input state already satisfies the full plan.

Keep the existing CLI module and package name. Do not use network access.
