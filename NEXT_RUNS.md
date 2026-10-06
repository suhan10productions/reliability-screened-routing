# Remaining runs, in order

Run these on your own machine from the package root, with six workers. Total
time is roughly two to two and a half hours. Set `OPENBLAS_NUM_THREADS=1` and
`OMP_NUM_THREADS=1` for every command.

## 0. Freeze the confirmatory protocol (before anything else)

```bash
PYTHONPATH=code python code/freeze_manifest.py
git add CONFIRMATORY_PROTOCOL.md FROZEN_MANIFEST.json && git commit -m "Freeze confirmatory protocol"
git push    # to a public repository; record the commit hash
```

From here on, do not edit any file listed in `FROZEN_MANIFEST.json`.

## 1. Confirmatory study (weakness 1), about 40 minutes

Run the three commands in `CONFIRMATORY_PROTOCOL.md`, exactly as written.
The last one prints the verdicts.

## 2. AHP weight sensitivity (weakness 3), about 70 minutes

```bash
PYTHONPATH=code python code/weight_sensitivity.py --workers 6
PYTHONPATH=code python code/weight_sensitivity.py --summarise
```

Four weight vectors on the 53 development instances: a rerun of the original
weights (measuring run-to-run variation), equal weights, slack-first, and
distance-heavy. Exploratory.

## 3. Solomon benchmark (weakness 2), about 20 minutes

```bash
PYTHONPATH=code python code/solomon_benchmark.py --workers 6
PYTHONPATH=code python code/solomon_benchmark.py --summarise
```

Eight 100-customer Solomon instances with the paper's time-dependent profile
and disturbance model. Exploratory. Expect R101 to return no OR-Tools plan:
HGS finds a 20-route plan for it, so this is a search limit of the generator,
and the failure policy records it.

Steps 2 and 3 use new scripts that do not modify any frozen file, so they can
run after step 1 without affecting it.

## 4. Send back

- the output of the confirmatory analysis command, and `results/confirm/`
- `results/weight_sensitivity_summary.json` and `results/weight_sensitivity/`
- `results/solomon_summary.json` and `results/solomon/`
- your hardware and the elapsed times

The results then go into the paper, whatever they show.
