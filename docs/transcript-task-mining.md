# Transcript Task Mining

This workflow mines George's local Codex and Claude transcripts for private ShallowSWE task
candidate patterns. The output is an authoring aid, not benchmark content.

Keep the first pass private. Transcript wording, project names, paths, customer context, and source
messages should stay under ignored `tmp/` until a candidate has been rewritten from scratch.

## Public and Private Repos

`lydakis/ShallowSWE` is public. Keep it as the home for reusable methodology, schema, extraction
code, scoring code, public task fixtures, and publishable benchmark results.

Create a separate private repo for transcript-mined material, for example
`/Users/lydakis/Developer/ShallowSWE-private` backed by a private GitHub repository. That repo can
hold:

- raw private mining outputs copied from `tmp/transcript-mining/<date>/`,
- private pattern cards that cite transcript source ids,
- sanitized but still unpublished Pier task drafts,
- private calibration configs and outputs,
- review notes that mention real source projects or customer context.

Do not publish the private repo or mirror its raw candidate JSONL into the public repo. A candidate
can move back to public ShallowSWE only after the sanitization pass removes all transcript wording,
real identifiers, source paths, private project names, and source-specific fixture data.

## Source Roots

Default inputs:

- Codex: `~/.codex/sessions/**/*.jsonl`
- Claude: `~/.claude/projects/**/*.jsonl`

The extractor reads user requests and queued Claude prompts. It skips system/context messages,
developer instructions, and local command caveats. By default it selects only requests whose source
path, working directory, or Claude project contains `ShallowSWE`; add explicit `--source-project`
values for any private project you intentionally include.

## Private Mining Command

Use a dated ignored output directory:

```bash
uv run python scripts/mine_transcript_candidates.py \
  --out-dir tmp/transcript-mining/2026-07-08
```

For a private project, add both a source filter and a scoring hint without baking its name into the
public tool:

```bash
uv run python scripts/mine_transcript_candidates.py \
  --source-project '<private-project>' \
  --repo-hint '<private-project>' \
  --out-dir tmp/transcript-mining/2026-07-08
```

The command refuses to write raw transcript output into a tracked public-repo path. Inside this
repository, output must stay under ignored `tmp/`; a separate private repository path is also valid.

Add `--max-candidates 500` only when you want a smaller review queue instead of the full mined
candidate set.

Generated files:

- `candidates.jsonl`: private candidate records with raw request excerpts.
- `summary.json`: aggregate counts and top candidate metadata.
- `summary.md`: quick private triage view.
- `inventory.json`: source roots, request counts, and schema version.

Do not move `candidates.jsonl` into tracked docs. Promote only rewritten pattern cards.

## Candidate Schema

Each JSONL row uses `shallowswe.transcript_candidate.v0.1` and stores:

- `source`: transcript system, path, line, timestamp, session id, cwd, and Claude project.
- `coding`: `category`, `size_hypothesis`, `maintenance_type`, `shape`, strength, score, signals.
- `privacy`: sensitivity label and sanitization plan.
- `benchmarking`: verifier idea, readiness, and next step.
- `raw_request_excerpt`: private truncated source wording for author review.

The public ShallowSWE axes remain:

- `category = code | artifact | workflow`
- `size = small | medium | large`

Mining-only labels such as sensitivity, shape, score, and readiness are triage metadata, not public
benchmark fields.

## Sanitization Pass

For every candidate worth keeping:

1. Rewrite the prompt from scratch as a normal delegated engineering ticket.
2. Replace project, company, person, path, repo, and service names.
3. Convert real state into small synthetic fixtures.
4. Remove transcript excerpts and source paths from any tracked artifact.
5. Record only the abstract source pattern and contamination notes.
6. Draft a verifier that tests observable behavior, not the reference implementation.

High-sensitivity candidates must become abstract pattern cards before leaving `tmp/`.

## Promotion Gate

Promote a mined candidate only when it can satisfy the normal ShallowSWE gates:

- Realistic routine work.
- Clear prompt without source transcript context.
- Offline deterministic Pier environment.
- Programmatic verifier with acceptance breadth.
- No copied text, data, tests, paths, or identifiers.
- Pre-registered category, size hypothesis, and calibration expectation.

## Calibration Handoff

After sanitized task cards exist, calibrate the shortlist like other ShallowSWE candidates:

1. Run task metadata validation with `uv run shallowswe tasks tasks`.
2. Estimate any panel before broad execution with `shallowswe estimate-panel ... --max-budget-usd ... --fail-over-budget`.
3. Use cheap Codex sizing probes for provisional bands only.
4. Spend higher-N repair-loop calibration only on candidates that pass prompt, verifier, and contamination review.

Small-N transcript-mined results should be labeled provisional until rerun under the normal
calibration protocol.
