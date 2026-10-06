# Completion guide

Six stages, in this order. Stages 1-4 need your computer; stage 5 can happen
while stage 4 runs.

## Stage 1. Set up (about 20 minutes, once)

1. Unzip `relscreen_v19_package.zip` into a folder, for example
   `reliability-screened-routing`.
2. Install Python 3.12 from python.org. The archived runs used 3.12.14.
3. Open a terminal in that folder and create an environment:

   macOS / Linux:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Windows (PowerShell):
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. Set these once in every new terminal session:

   macOS / Linux: `export PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`

   Windows: `$env:PYTHONPATH="code"; $env:OPENBLAS_NUM_THREADS="1"; $env:OMP_NUM_THREADS="1"`
5. Check that everything works. Both must succeed before you go further:
   ```bash
   python -m unittest discover -s tests          # must end with "OK"
   python code/check_confirmatory_safeguards.py  # must end with "ALL SAFEGUARDS BEHAVE AS SPECIFIED"
   ```
   (The commands below are written in macOS/Linux form; with the variables set
   as in step 4, the `python ...` part is identical on Windows.)

## Stage 2. Freeze the protocol publicly (about 30 minutes)

1. Create a free GitHub account and a new **public** repository with a neutral
   name, for example `reliability-screened-routing`. Do not add a README there.
2. Create a free Zenodo account by signing in with GitHub. Under
   *GitHub* in your Zenodo settings, switch the new repository **on**. This
   must happen before step 5, or Zenodo will not archive the release.
3. Write the manifest, which fingerprints the protocol and code:
   ```bash
   python code/freeze_manifest.py
   ```
4. Commit and push everything:
   ```bash
   git init
   git add .
   git commit -m "Freeze confirmatory protocol"
   git branch -M main
   git remote add origin https://github.com/YOUR-NAME/reliability-screened-routing.git
   git push -u origin main
   git rev-parse HEAD        # copy this commit hash and keep it
   ```
   `.gitignore` keeps your private checklist out automatically.
5. On GitHub, create a release named `protocol-freeze`. Zenodo will give it a
   DOI within a few minutes. That DOI is your timestamped proof that the
   hypotheses came before the results.
6. From now on, do not edit any file listed in `FROZEN_MANIFEST.json`.

## Stage 3. Run the confirmatory study (about 40 minutes)

Run the three commands in `CONFIRMATORY_PROTOCOL.md` under "Procedure", exactly
as written, in order. On Windows, the variables are already set from stage 1,
so leave out the `PYTHONPATH=... OMP_NUM_THREADS=1` prefix, and replace the
`for` loop with four separate commands:

```powershell
python code/study_v6.py --sizes 20  --seed-shift 60000 --output results/confirm/study_v6_n20.json
python code/study_v6.py --sizes 50  --seed-shift 60000 --output results/confirm/study_v6_n50.json
python code/study_v6.py --sizes 100 --seed-shift 60000 --output results/confirm/study_v6_n100.json
python code/study_v6.py --sizes 200 --seed-shift 60000 --output results/confirm/study_v6_n200.json
``` The last command prints each hypothesis with
CONFIRMED or NOT CONFIRMED. Save that output to a text file.

## Stage 4. Run the two exploratory analyses (about 90 minutes)

```bash
python code/weight_sensitivity.py --workers 6
python code/weight_sensitivity.py --summarise
python code/solomon_benchmark.py --workers 6
python code/solomon_benchmark.py --summarise
```

Rules for all runs in stages 3 and 4:

- Keep the computer awake and plugged in.
- If a run is interrupted, run the same command again. Every script resumes
  from where it stopped.
- If you see `SOFTWARE ERROR` or `PROTOCOL VIOLATION`, stop and send the
  output. Do not fix the code yourself: after the freeze, any code change is a
  deviation that has to be reported.
- Expect R101 to return no OR-Tools plan in the Solomon run. That is a known
  generator search limit, already recorded by the failure policy.

Then send back: the confirmatory output text; the folders `results/confirm/`,
`results/weight_sensitivity/` and `results/solomon/`; the two summary JSON
files; and your computer's processor, memory and operating system.

## Stage 5. Tasks to do while the runs go

1. **Email Vidal** (draft provided earlier). Note one change: the
   acknowledgement now says "deterministic vehicle-routing benchmarking"
   instead of "VRPTW".
2. **AI tool names.** Check the exact model names in each app's settings and
   correct the AI paragraph if needed.
3. **Competing interests.** The journal's test: would an undeclared interest
   embarrass you if it became public after publication? If RouteOps Engine
   has users or revenue, declare it.
4. **Suggested reviewers** (3 to 5). Each must be independent: not anyone you
   emailed about this work, not anyone acknowledged, not a co-author of yours.
   Search your sent mail before choosing. Good sources are the authors of
   papers you cite and of recent stochastic VRPTW papers in EJOR,
   Transportation Science or Computers & Operations Research. Prefer different
   countries. For each, note name, institution, country, and an institutional
   email or a public profile link.
5. **Preprint route.** Create an Optimization Online account, and decide whether
   to ask an established author for an arXiv endorsement.
6. **OR-Tools link.** Open https://developers.google.com/optimization, confirm
   it works, and note the date for the reference's access date.
7. **Title.** Decide whether to shorten it; the journal asks for a concise one.

## Stage 6. Finish and submit (after you send the results)

1. I write the results into the paper: confirmatory verdicts, weight
   sensitivity and Solomon benchmark, with the abstract and conclusion updated
   to match, whatever the outcome. I also draft the cover letter.
2. You push the final version to GitHub and create a release named `v1.0`.
   Zenodo gives it a new DOI.
3. I put that DOI into the data availability statement and rebuild the
   submission files.
4. You post the preprint and note its DOI and licence.
5. Submit through the journal's "Submit manuscript" link:
   - article type: original research article;
   - upload every file in `submission/`, plus the package renamed `ESM_1.zip`
     (`ESM_1_README.txt` is already inside);
   - enter title, abstract, keywords and ORCID;
   - enter competing interests, funding (none) and author contributions in the
     form itself: only what is entered there is published;
   - give the data availability statement with the Zenodo DOI, the preprint
     DOI and licence, the suggested reviewers, and the cover letter;
   - choose the free subscription route if asked after acceptance.
