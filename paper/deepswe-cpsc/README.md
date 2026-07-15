# DeepSWE CPSC Working Paper

This directory contains the reproducible working paper associated with the historical A1--A3 plan
in `docs/deepswe-cpsc-preanalysis.md` and the explicit A4--A5 supplement in
`docs/deepswe-cpsc-amendments-v0.2.md`.

## Reproduce

Download the four DeepSWE v1.1 artifacts listed in `configs/deepswe-cpsc-v0.2.json`, then verify
their byte counts and SHA-256 hashes. With the trials and leaderboard artifacts at the paths below:

```bash
uv run python -m shallowswe.deepswe_economics \
  /tmp/deepswe-v1.1-trials.json \
  /tmp/deepswe-v1.1-leaderboard.json \
  --plan configs/deepswe-cpsc-v0.2.json \
  --output /tmp/deepswe-cpsc-v0.2-report.json

uv run python -m shallowswe.deepswe_paper \
  /tmp/deepswe-v1.1-trials.json \
  /tmp/deepswe-cpsc-v0.2-report.json \
  paper/deepswe-cpsc/generated

(cd paper/deepswe-cpsc && tectonic -X compile main.tex)
```

The checked-in PNGs are static exports of the generated SVG figures and exist only for portable TeX
compilation. `generated/manifest.json` hashes every generated table, figure, and summary file except
itself. Generated tables include observed-attempt and equal-task workload estimands, resource
intensity and paired resource comparisons, outcome-derived panel-solvedness diagnostics, reliability
policy reselection, and two retrospective proxy failure-charge constructions. The original v0.1
files are preserved byte-for-byte; result-informed extensions A4 and A5 are versioned separately.

## Evidence boundary

The paper is a retrospective external reanalysis. It demonstrates that realized-cost accounting and
task-clustered stability analysis transport coherently to a frontier benchmark. It separates
reported-invoice efficiency from recorded resource appetite and documents workload-, reliability-,
failure-price-, and price-basis dependence. It does not validate a production workload construct,
calibrated reference budgets, replacement costs, a repair-loop protocol, or production routing
economics.
