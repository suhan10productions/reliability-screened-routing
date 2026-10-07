# Confirmatory study 2: run sheet (macOS)

About 1.5 hours of computer time. Work in the project folder, in the
`relscreen` conda environment, with the Mac plugged in and otherwise idle, and
keep `caffeinate -i` running in a second Terminal window.

Copy only the lines inside the code boxes. Do not paste the plain-text notes.

**Do steps in order. Step 3 must print `FREEZE VERIFIED` before step 4.**

## 1. Apply the update and set the earlier run aside

```bash
cd ~/Desktop/relscreen_v20_package
conda activate relscreen
export PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
unzip -o ~/Downloads/overlay_v27.zip
mkdir -p results/abandoned_70000
mv results/confirm2/* results/abandoned_70000/
rmdir results/confirm2
rm -f confirm2_results.zip
```

The earlier run used seeds that were solved before the protocol was frozen, so
they are kept but never analysed (the protocol discloses this).

## 2. Check, commit and push the update

```bash
python -m unittest discover -s tests
python code/check_hgs_safeguards.py
git add .
git status
```

The tests must end with `OK` (18 tests), the checker with
`ALL SAFEGUARDS BEHAVE AS SPECIFIED`, and `git status` must list no `.zip`
files. Then:

```bash
git commit -m "Add HGS generator, development run, protocol 2 (proposed) and the abandoned run"
git push
```

## 3. Freeze, then verify the freeze

```bash
python code/freeze_manifest_hgs.py
git add CONFIRMATORY_PROTOCOL_2.md FROZEN_MANIFEST_2.json
git commit -m "Freeze confirmatory protocol 2"
git push
```

On GitHub: **Releases → Draft a new release → in "Choose a tag" type
`protocol-2-freeze` → Create new tag → Publish release.** Check on Zenodo that
a new record appears. Then:

```bash
git fetch --tags
python code/check_freeze_2.py
```

It must print `FREEZE VERIFIED`. If it prints anything else, stop and send it
to me. From now on, edit nothing listed in `FROZEN_MANIFEST_2.json`.

## 4. OR-Tools half, stage 1 (about 40 minutes)

```bash
mkdir -p results/confirm2
for n in 20 50 100 200; do python code/study_v6.py --sizes $n --seed-shift 80000 --output results/confirm2/study_v6_n$n.json > results/confirm2/log_n$n.txt 2>&1 & done; wait
python -c "import json,glob; [print(f, len(json.load(open(f))['records']), 'records,', len(json.load(open(f)).get('software_errors',[])), 'software errors') for f in sorted(glob.glob('results/confirm2/study_v6_n*.json'))]"
```

Expect 10, 20, 8 and 15 records (alphabetical order), each with 0 software
errors.

## 5. OR-Tools half, stage 2 (about 12 minutes)

```bash
python code/study_v7.py --inputs results/confirm2/study_v6_n20.json results/confirm2/study_v6_n50.json results/confirm2/study_v6_n100.json results/confirm2/study_v6_n200.json --output results/confirm2/v7 --workers 6 --seconds 5
ls results/confirm2/v7 | wc -l
```

Expect 53.

## 6. HGS half (about 20 to 30 minutes)

```bash
python code/study_hgs.py --seed-shift 80000 --output results/confirm2/hgs --workers 6
ls results/confirm2/hgs | wc -l
```

Expect 53.

## 7. The analysis (seconds)

```bash
python code/confirm_analysis_hgs.py confirmatory --stage1 results/confirm2/study_v6_n20.json results/confirm2/study_v6_n50.json results/confirm2/study_v6_n100.json results/confirm2/study_v6_n200.json --stage2 results/confirm2/v7 --hgs results/confirm2/hgs --manifest FROZEN_MANIFEST_2.json | tee results/confirm2/analysis_output.txt
zip -r confirm2_results.zip results/confirm2
```

## If anything goes wrong

- Interrupted: rerun the same command; every step resumes.
- `SOFTWARE ERROR`, `PROTOCOL VIOLATION` or `FREEZE NOT VERIFIED`: stop and send
  the output. Do not edit code.

## Send back

`results/confirm2/analysis_output.txt`, `confirm2_results.zip`, the freeze
commit hash, the Zenodo DOI of `protocol-2-freeze`, and roughly how long each
step took.
