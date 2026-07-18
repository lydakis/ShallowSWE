# Codex Subscription Sizing

Tasks: 2

## Formal Ceiling

- Model config: `openai/gpt-5.5[extra_high]`
- Medium smoke rows, when present, are not formal ceiling evidence.
- Passed: 1
- Failed: 1
- Excluded: 0
- Pending: 0

## Provisional Floor Sizes

- `small`: 1
- `medium`: 0
- `large`: 1
- `None`: 0

## Tasks

| Task | Metadata | Floor Probe | Formal Ceiling | Medium Smoke |
| --- | --- | --- | --- | --- |
| `config-key-rollover` | large | small (1/1) | 1/1 | pending |
| `incident-comms-pipeline` | large | large (0/1) | 0/1 | pending |
