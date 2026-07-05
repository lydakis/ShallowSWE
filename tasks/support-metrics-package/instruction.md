# Produce Support Metrics Package

Build support metrics under `output/` from the CSV files in `input/`.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Agent summary includes ticket and breach counts.
- SLA breaches list only over-target tickets.
- Summary includes totals and escalation count.
- Write exactly these files under `output/`:
  - `summary.json` with keys `escalations`, `sla_breaches`, and `tickets`.
  - `agent_summary.csv` with columns `agent_id,name,tickets,sla_breaches`.
  - `sla_breaches.csv` with columns `ticket_id,agent_id,priority,response_minutes,target_minutes`.
- Count an SLA breach when `response_minutes` is greater than the target for that ticket priority.
- Sort `agent_summary.csv` by `agent_id`.
- Sort `sla_breaches.csv` by `ticket_id`.

Keep the work local to this repository. Do not use network access.
