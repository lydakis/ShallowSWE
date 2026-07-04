# Build Release Checklist From Spec

Read `input/release-spec.md` and create `output/checklist.json`.

The input bullets have this form:

```text
- [required][ops] Confirm migration dry run
- [optional][growth] Draft launch post
```

For each matching bullet, write one JSON object with these fields:

- `id`: `rel-1`, `rel-2`, ... using the 1-based bullet position in document order.
- `title`: the text after the two bracket markers.
- `owner`: the value in the second bracket marker.
- `required`: `true` for `[required]`, `false` for `[optional]`.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Items stay in document order.
- Required and optional markers are preserved.
- Owners are preserved.
- Do not modify files under `input/`; only write `output/checklist.json`.

Keep the work local to this repository. Do not use network access.
