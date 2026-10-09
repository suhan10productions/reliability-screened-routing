"""Manuscript text, tables and macros for the family-wise screening check, the
run-time and buffer summaries, and the misspecified delay models (all exploratory).

Reads results/family_wise_summary.json (code/analyse_family_wise.py),
results/timing_components.json (code/time_components.py),
results/misspecification.json (code/misspecification.py) and the stored
selections in the study records. Writes paper/result_macros_v11.tex and
paper/checks_results.tex.
"""
from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path

import numpy as np

from analyse_robust import boot
from relscreen_v6 import wilson_lower_bound

VALIDATION_SCENARIOS, ETA, ALPHA = 5000, 0.05, 0.95

ROOT = Path(__file__).resolve().parents[1]


def f1(x):
    return f"{x:.1f}".replace("-", "$-$")


def iv(m):
    return f"{f1(m[0])} [{f1(m[1])}, {f1(m[2])}]"


def tab(caption, label, cols, header, rows, size="footnotesize"):
    return "\n".join([r"\begin{table}[htbp]", r"\centering", f"\\{size}", r"\setlength{\tabcolsep}{4pt}",
                       f"\\caption{{{caption}}}",
                      f"\\label{{{label}}}", f"\\begin{{tabular}}{{{cols}}}", r"\toprule", header + r"\\",
                      r"\midrule", *[r + r"\\" for r in rows], r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])


def selected_betas(s1dir, v7dir, hgsdir):
    st = {}
    for f in glob.glob(str(ROOT / s1dir / "study_v6_n*.json")):
        for r in json.loads(Path(f).read_text())["records"]:
            st[r["instance_seed"]] = r
    ort, hgs = Counter(), Counter()
    for f in glob.glob(str(ROOT / v7dir / "instance_*.json")):
        r = json.loads(Path(f).read_text())
        for plan in (st[r["instance_seed"]]["screened"]["selected_plan"], r["capped_procedure"]["selected_plan"]):
            if plan:
                ort[plan["beta"]] += 1
    if hgsdir:
        for f in glob.glob(str(ROOT / hgsdir / "instance_*.json")):
            r = json.loads(Path(f).read_text())
            if r["selected"]["capped"]:
                hgs[r["selected_beta"]["capped"]] += 1
    return ort, hgs


def rescreen_section(labels):
    """Paragraph and table for re-screening under each alternative model (misspecification_rescreen.py)."""
    path = ROOT / "results/misspecification_rescreen.json"
    if not path.exists():
        return [], {}
    rs = json.loads(path.read_text())["summary"]
    models = list(rs)
    m = lambda model, k: rs[model][k]["mean"]
    rows = [f"{labels[x]} & " + " & ".join(f1(m(x, k)) for k in (
        "ort_capped", "ort_rescreened", "ort_rescreened_best", "hgs_capped_cons", "hgs_rescreened",
        "hgs_rescreened_best")) for x in models]
    # the sentences rely on these patterns
    harsh = ("incidents", "strong_peak")
    assert rs["peak_noise"]["hgs_rescreened_minus_fixed"][2] < 0
    for x in harsh:
        assert rs[x]["ort_rescreened_minus_fixed"][2] < 0 and rs[x]["hgs_rescreened_minus_fixed"][2] < 0, x
    for x in models:
        for t in ("ort", "hgs"):
            assert rs[x][f"{t}_rescreened_best_minus_fixed"][1] > 0, (x, t)
    assert rs["baseline"]["ort_rescreened_minus_fixed"][0] == 0 and rs["baseline"]["hgs_rescreened_minus_fixed"][0] == 0
    worst_drop = max(-rs[x][f"{t}_rescreened_minus_fixed"][0] for x in harsh for t in ("ort", "hgs"))
    lo_ort = min(m(x, "ort_rescreened_best") for x in models)
    hi_ort = max(m(x, "ort_rescreened_best") for x in models)
    lo_hgs = min(m(x, "hgs_rescreened_best") for x in models)
    hi_hgs = max(m(x, "hgs_rescreened_best") for x in models)
    adm = {x: (rs[x]["ort_admitted"], rs[x]["hgs_admitted"]) for x in models}
    k_ort = rs["baseline"]["ort_capped"]["instances"]
    k_hgs = rs["baseline"]["hgs_capped_cons"]["instances"]
    text = [
        "Re-screening asks what the procedure itself would do under each model. Every stored candidate "
        "of the capped families was screened again on 1000 scenarios drawn from that model (seed 100000 plus the "
        "instance seed), the selection rule was applied unchanged, and the selected plan was validated on the same "
        "5000 scenarios of that model. The candidate families were not regenerated. Under the paper's model this "
        "reproduces every stored selection, which the script checks. Table~\\ref{tab:rescreen} reports two "
        "fallbacks for instances where nothing is admitted: the procedure's stored fallback, and the candidate "
        "with the highest screening success (Section~\\ref{sec:fallback}).", "",
        tab("Re-screening under each delay model (exploratory): pooled service-event probability (\\%) of the "
            f"capped procedures over {k_ort} OR-Tools and {k_hgs} HGS instances. Fixed: the stored plans. "
            "Re-screened: the stored candidates screened again under the model, with the stored fallback. Best: "
            "the same, with the best-screened fallback.",
            "tab:rescreen", r"@{}lrrrrrr@{}",
            r"Delay model & \multicolumn{3}{c}{OR-Tools capped} & \multicolumn{3}{c}{HGS capped}\\" "\n"
            r" & Fixed & Re-screened & Best & Fixed & Re-screened & Best", rows),
        "With the stored fallback, re-screening did worse than keeping the fixed plans under incidents and the "
        f"stronger peak, by up to {f1(worst_drop)} points, and for HGS also under time-of-day noise. Fewer candidates passed under these models (OR-Tools "
        f"{adm['incidents'][0]} and {adm['strong_peak'][0]} admissions against {adm['baseline'][0]} under the "
        "paper's model), and the instances that failed received the weak stored fallback. With the best-screened "
        "fallback, re-screening exceeded the fixed plans under every model, and pooled service stayed between "
        f"{f1(lo_ort)} and {f1(hi_ort)}\\% for OR-Tools and between {f1(lo_hgs)} and {f1(hi_hgs)}\\% for HGS.", "",
    ]
    macros = {"ResLoOrt": f1(lo_ort), "ResHiOrt": f1(hi_ort), "ResLoHgs": f1(lo_hgs), "ResHiHgs": f1(hi_hgs),
              "ResWorstDrop": f1(worst_drop)}
    return text, macros


def main():
    fw = json.loads((ROOT / "results/family_wise_summary.json").read_text())
    tm = json.loads((ROOT / "results/timing_components.json").read_text())
    ms = json.loads((ROOT / "results/misspecification.json").read_text())

    # ---- family-wise screening ----
    names = {"original": "Original (OR-Tools)", "capped": "Capped (OR-Tools)",
             "hgs_capped_cons": "HGS capped, conservative fallback"}
    lcb_ok = lambda service: wilson_lower_bound(service / 100, VALIDATION_SCENARIOS, ETA) >= ALPHA
    fw_rows, changed_pts, lost = [], [], []
    tot = Counter()
    words = {0: "no", 1: "one", 2: "two", 3: "three"}
    for study, procs in fw["studies"].items():
        for proc, v in procs.items():
            adm = [r for r in v["rows"] if r["orig_admitted"]]
            kept = sum(lcb_ok(r["orig_service"]) for r in adm)
            for r in v["rows"]:      # the stored flag and the recomputed bound agree
                if r["fw_admitted"]:
                    assert lcb_ok(r["fw_service"]) == r["fw_lcb_ok"], (study, proc, r["seed"])
            assert len(adm) == v["admitted_original"]
            fw_rows.append(f"{study.capitalize()} & {names[proc]} & {len(adm)} & {kept} & {f1(v['pooled_original'])} & "
                           f"{v['admitted_family_wise']} & {v['family_wise_admitted_retained']} & "
                           f"{f1(v['pooled_family_wise'])}")
            tot.update(adm=len(adm), kept=kept, adm_fw=v["admitted_family_wise"],
                       kept_fw=v["family_wise_admitted_retained"], combos=1,
                       switched=sum(r["changed"] and r["fw_admitted"] for r in adm))
            # every admitted plan that missed the validation bound is no longer selected, and every
            # family-wise miss is a newly selected plan; the sentence in the text relies on both
            for r in adm:
                if not lcb_ok(r["orig_service"]):
                    assert (not r["fw_admitted"]) or r["changed"], (study, proc, r["seed"])
            new_miss = [r for r in v["rows"] if r["fw_admitted"] and not r["fw_lcb_ok"]]
            assert all(r["changed"] for r in new_miss), (study, proc)
            tot.update(new_miss=len(new_miss))
            changed_pts.append(v["pooled_family_wise"] - v["pooled_original"])
            lost.append(v["admitted_original"] - v["admitted_family_wise"])
    adm_means = [v["family_wise_admitted_mean_service"] for p in fw["studies"].values() for v in p.values()]
    orig_adm_means = [float(np.mean([r["orig_service"] for r in v["rows"] if r["orig_admitted"]]))
                      for p in fw["studies"].values() for v in p.values()]

    # ---- timing and buffers ----
    med = tm["median_by_size"]
    betas = {k: selected_betas(*d) for k, d in {
        "development": ("results", "results/v7", "results/hgs_dev"),
        "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
        "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs")}.items()}
    ort_all = sum((b[0] for b in betas.values()), Counter())
    hgs_all = sum((b[1] for b in betas.values()), Counter())
    ort_n, hgs_n = sum(ort_all.values()), sum(hgs_all.values())
    ort_mid = sum(c for b, c in ort_all.items() if 25 <= b <= 45)
    ort_med = float(np.median([b for b, c in ort_all.items() for _ in range(c)]))
    hgs_med = float(np.median([b for b, c in hgs_all.items() for _ in range(c)]))

    # ---- misspecification, pooled over studies ----
    models = ms["models"]
    labels = {"baseline": "Paper's model (new scenarios)", "heavy_tails": "Heavy tails", "incidents": "Incidents",
              "peak_noise": "Time-of-day noise", "strong_peak": "Stronger morning peak"}
    configs = [("ort_conservative", "Cons."), ("ort_original", "Original"), ("ort_capped", "Capped"),
               ("hgs_conservative", "HGS cons."), ("hgs_capped_cons", "HGS capped"), ("screened_relief", "Scr.\\ robust")]
    pairs = [("ort_original", "ort_conservative"), ("ort_capped", "ort_conservative"),
             ("hgs_capped_cons", "hgs_conservative"), ("screened_relief", "hgs_capped_cons")]
    rows_all = [r for s in ms["studies"].values() for r in s["rows"]]
    pooled, contrasts = {}, {}
    for m in models:
        pooled[m] = {}
        for c, _ in configs:
            vals = [r["service"][m][c] for r in rows_all if c in r["service"][m]]
            pooled[m][c] = (float(np.mean(vals)), len(vals))
        contrasts[m] = {}
        for x, y in pairs:
            rs = [r for r in rows_all if x in r["service"][m] and y in r["service"][m]]
            contrasts[m][(x, y)] = (boot([r["service"][m][x] - r["service"][m][y] for r in rs]), len(rs))
    ms_rows = [f"{labels[m]} & " + " & ".join(f1(pooled[m][c][0]) for c, _ in configs) for m in models]
    ct_rows = [f"{labels[m]} & " + " & ".join(iv(contrasts[m][xy][0]) for xy in pairs) for m in models]
    k_ort = pooled["baseline"]["ort_capped"][1]
    k_hgs = pooled["baseline"]["hgs_capped_cons"][1]
    k_rob = pooled["baseline"]["screened_relief"][1]
    low = lambda xy: min(contrasts[m][xy][0][1] for m in models)
    min_orig, min_ort, min_hgs = low(pairs[0]), low(pairs[1]), low(pairs[2])
    # differences of the displayed (rounded) table values, so the text matches the table
    r1 = lambda x: round(x, 1)
    drop = lambda m, c: r1(pooled["baseline"][c][0]) - r1(pooled[m][c][0])
    capped_drop = max(drop(m, c) for m in models for c in ("ort_capped", "hgs_capped_cons"))
    cons_drop = max(drop(m, c) for m in models for c in ("ort_conservative", "hgs_conservative"))
    ht_gain_cons = r1(pooled["heavy_tails"]["ort_conservative"][0])
    rob = lambda m: contrasts[m][pairs[3]][0]
    # the sentences below rely on these patterns; stop if the data do not show them
    for c, _ in configs:
        assert pooled["heavy_tails"][c][0] >= pooled["baseline"][c][0], c
        for m in ("incidents", "peak_noise", "strong_peak"):
            assert pooled[m][c][0] < pooled["baseline"][c][0], (m, c)
    for c in ("ort_capped", "hgs_capped_cons", "screened_relief"):
        assert abs(drop("heavy_tails", c)) < 1, c
    for c in ("ort_capped", "hgs_capped_cons", "ort_conservative", "hgs_conservative"):
        assert max(models, key=lambda m: drop(m, c)) == "strong_peak", c
        assert sorted(models, key=lambda m: drop(m, c))[-2] == "incidents", c
    assert all(rob(m)[0] > 0 for m in models)
    rob_zero = [m for m in models if rob(m)[1] <= 0]
    assert rob_zero == ["peak_noise", "strong_peak"], rob_zero
    assert all(contrasts[m][xy][0][1] > 0 for m in models for xy in pairs[:3])

    rescreen_text, rescreen_macros = rescreen_section(labels)
    macros = {
        "FwAdmittedOrig": str(tot["adm"]), "FwAdmittedTotal": str(tot["adm_fw"]),
        "FwMissOrig": str(tot["adm"] - tot["kept"]), "FwMissFw": str(tot["adm_fw"] - tot["kept_fw"]),
        "FwLostMax": str(max(lost)), "FwPooledChangeMin": f1(min(changed_pts)), "FwPooledChangeMax": f1(max(changed_pts)),
        "FwAdmMeanMin": f1(min(adm_means)), "FwAdmMeanMax": f1(max(adm_means)),
        "AdmMeanMin": f1(min(orig_adm_means)), "AdmMeanMax": f1(max(orig_adm_means)),
        "TimeScreenTwenty": f"{1000 * med['20']['screen_median']:.0f}",
        "TimeScreenTwoHundred": f"{1000 * med['200']['screen_median']:.0f}",
        "TimeHgsTwenty": f1(med["20"]["hgs_median"]), "TimeHgsTwoHundred": f1(med["200"]["hgs_median"]),
        "BetaOrtMid": str(ort_mid), "BetaOrtN": str(ort_n), "BetaOrtEdge": str(ort_all.get(60, 0)),
        "BetaHgsEdge": str(hgs_all.get(60, 0)), "BetaHgsN": str(hgs_n),
        "MisMinOrig": f1(min_orig), "MisMinOrt": f1(min_ort), "MisMinHgs": f1(min_hgs),
        "MisCappedDrop": f1(capped_drop), "MisConsDrop": f1(cons_drop),
        "MisKOrt": str(k_ort), "MisKHgs": str(k_hgs), "MisKRob": str(k_rob),
        **rescreen_macros,
    }
    (ROOT / "paper/result_macros_v11.tex").write_text(
        "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k, v in macros.items()) + "\n")

    text = [
        r"\section{Further exploratory checks}\label{sec:checks}", "",
        "The three checks in this appendix were added after both confirmatory studies and are "
        "exploratory. The first reuses the stored screening counts, the second times screening and one HGS solve on "
        "each development instance and counts the selected buffers, and the third evaluates the stored plans on new "
        "scenarios. The misspecification check also reruns the selection under each alternative model.", "",
        r"\subsection{Family-wise screening}\label{sec:familywise}", "",
        "The admission bound holds for each candidate separately, while the procedure searches 13 buffer levels per "
        "instance. To check whether this matters, every stored candidate family was screened again with the Wilson "
        "bound at $\\eta/13$, a Bonferroni adjustment that makes the 95\\% bound hold simultaneously over the grid. "
        "Selection and fallback were otherwise unchanged, and any newly selected plan was validated on the original "
        f"fresh bank (Table~\\ref{{tab:familywise}}). Over the {tot['combos']} combinations of study and procedure, the "
        f"adjustment reduced the admitted instances from {tot['adm']} to {tot['adm_fw']}, at most {max(lost)} per "
        f"combination, and selected a different plan on {tot['switched']} of the instances it still admitted. "
        f"Admitted plans whose validation lower bound fell below 0.95 went from {tot['adm'] - tot['kept']} of "
        f"{tot['adm']} to {tot['adm_fw'] - tot['kept_fw']} of {tot['adm_fw']}. Pooled service changed by between "
        f"{f1(min(changed_pts))} and {f1(max(changed_pts))} points. Admitted plans averaged "
        f"{f1(min(orig_adm_means))} to {f1(max(orig_adm_means))}\\% on the fresh bank under the per-candidate bound, "
        f"depending on study and procedure, and {f1(min(adm_means))} to {f1(max(adm_means))}\\% under the "
        f"family-wise bound. The stricter bound thus removed all {tot['adm'] - tot['kept']} admitted plans whose "
        f"validation bound fell below 0.95, while {words.get(tot['new_miss'], tot['new_miss'])} plan"
        f"{'' if tot['new_miss'] == 1 else 's'} it newly selected fell below it, at the cost "
        f"of a few admissions and up to {f1(-min(changed_pts))} points of pooled service.", "",
        tab("Family-wise screening (exploratory). Adm.: instances with an admitted plan. Kept: admitted plans whose "
            "validation lower bound was at least 0.95. Pooled: validated service-event probability (\\%) of the "
            "procedure over all instances, fallbacks included. Columns marked FW use the Bonferroni bound over the "
            "13 buffer levels.",
            "tab:familywise", r"@{}l>{\raggedright\arraybackslash}p{3.1cm}rrrrrr@{}",
            r"Study & Procedure & Adm. & Kept & Pooled & Adm.\ FW & Kept FW & Pooled FW", fw_rows),
        r"\subsection{Computation time and buffer choice}\label{sec:time}", "",
        "Screening is cheap relative to generation. On one x86-64 Linux machine, evaluating one candidate on the "
        f"1000-scenario screening bank took a median of {1000 * med['20']['screen_median']:.0f}~ms at 20 customers "
        f"and {1000 * med['200']['screen_median']:.0f}~ms at 200. A candidate solve has a fixed five-second OR-Tools "
        f"budget, and a median HGS solve took {f1(med['20']['hgs_median'])}~s at 20 customers and "
        f"{f1(med['200']['hgs_median'])}~s at 200. The procedure's cost therefore lies in up to 13 candidate solves "
        "($\\beta=0$ to 60 minutes), each of which OR-Tools repeats at most twice if it returns no plan. Absolute "
        "times depend on the machine.", "",
        "Among admitted selections, the buffer grid was rarely binding for OR-Tools. Over the three studies, "
        f"{ort_mid} of the {ort_n} OR-Tools selections used a buffer between 25 and 45 minutes, and "
        f"{ort_all.get(60, 0)} used the largest buffer of 60 minutes; the median selected buffer was {ort_med:.0f} "
        f"minutes. HGS selected larger buffers (median {hgs_med:.0f} minutes), and {hgs_all.get(60, 0)} of its "
        f"{hgs_n} selections were at 60 minutes, so a wider grid could change some HGS selections. On instances where "
        "nothing was admitted, no buffer up to 60 minutes passed, and the grid cannot show whether a larger one "
        "would have.", "",
        r"\subsection{Misspecified delay models}\label{sec:misspec}", "",
        "The plans were screened under one assumed disturbance model. To test how much the conclusions depend on it, "
        "the stored plans of the development and both confirmatory studies were evaluated, without re-screening or "
        "re-optimization, on 5000 new scenarios per instance under four other models. The models were chosen before "
        "the run, but they were not registered. The heavy-tail model replaces the normal common and local "
        "log-errors by Student-$t$ errors with three degrees of freedom, scaled to the same variance. At equal "
        "variance these errors are more peaked near zero and have heavier tails, so the model changes the shape of "
        "the distribution more than its spread; the multipliers then have infinite mean, although every simulated "
        "value is finite. The incident model adds, on each arc traversal, an independent 3\\% chance that the "
        "travel time doubles. The time-of-day model uses $\\sigma=0.30$ and $\\rho=0.8$ for departures in the "
        "morning peak (07:00--09:00) and $\\sigma=0.15$ and $\\rho=0.3$ at other times, in place of $\\sigma=0.20$ "
        "and $\\rho=0.5$ throughout. (The code also raises the noise in the evening peak, which begins after every "
        "time window has closed and so has no effect.) The stronger-peak model divides speed by 1.4 between 07:00 "
        "and 09:00, where the plans assumed 1.2. Tables~\\ref{tab:misspec} and~\\ref{tab:misspec-contrasts} pool "
        f"the {k_ort} OR-Tools instances, the {k_hgs} HGS instances and the {k_rob} instances of the robust "
        "comparison.", "",
        tab("Misspecified delay models (exploratory): pooled service-event probability (\\%) of fixed plans on 5000 "
            f"new scenarios per instance. OR-Tools columns use {k_ort} instances, HGS columns {k_hgs} and screened "
            f"robust with relief {k_rob}; because the instance sets differ, configurations are compared in "
            "Table~\\ref{tab:misspec-contrasts}. Cons.: conservative speed. Original and Capped: the OR-Tools "
            "procedures. HGS capped: the HGS capped procedure with conservative fallback. "
            "A missing plan scores zero.",
            "tab:misspec", r"@{}lrrrrrr@{}",
            r"Delay model & Cons. & Original & Capped & HGS cons. & HGS capped & Scr.\ robust", ms_rows),
        tab("Misspecified delay models (exploratory): paired differences in service probability (percentage points) "
            "with 95\\% bootstrap intervals over instances. Cons.: conservative speed.",
            "tab:misspec-contrasts",
            r"@{}>{\raggedright\arraybackslash}p{2.5cm}>{\raggedright\arraybackslash}p{2.3cm}"
            r">{\raggedright\arraybackslash}p{2.3cm}>{\raggedright\arraybackslash}p{2.4cm}"
            r">{\raggedright\arraybackslash}p{2.4cm}@{}",
            r"Delay model & Original minus cons. & Capped minus cons. & HGS capped minus HGS cons. & "
            r"Scr.\ robust minus HGS capped", ct_rows),
        "Heavy tails did not lower service. Conservative speed gained most, from "
        f"{f1(pooled['baseline']['ort_conservative'][0])} to {f1(ht_gain_cons)}\\% for OR-Tools, and the capped "
        "procedures and screened robust changed by less than one point. The other three models lowered service for every "
        "configuration, most of all the stronger peak and then incidents. The stronger peak reduced the capped "
        f"procedures by up to {f1(capped_drop)} points and conservative speed by up to {f1(cons_drop)} points: "
        "travel in the morning peak now takes 40\\% longer than at nominal speed, which the 20\\% pad no longer "
        "covers. The advantage over conservative speed held under every model, with lower interval limits of at "
        f"least {f1(min_orig)} points for the original procedure, {f1(min_ort)} for the capped procedure and "
        f"{f1(min_hgs)} for the HGS capped procedure. On its {k_rob} instances, screened robust with relief stayed "
        f"ahead of the HGS capped procedure under every model, but its lead fell from {f1(rob('baseline')[0])} "
        f"to {f1(rob('peak_noise')[0])} points under time-of-day noise, and the intervals include zero under "
        "time-of-day noise and the stronger peak. These results concern fixed plans.", "",
        *rescreen_text,
    ]
    (ROOT / "paper/checks_results.tex").write_text("\n".join(text))
    summary = [
        r"\subsection{Further checks}\label{sec:checks-summary}", "",
        "Appendix~\\ref{sec:checks} reports three further exploratory checks. Repeating the selection with a "
        "Bonferroni bound over the 13 buffer levels removed all "
        f"{tot['adm'] - tot['kept']} admitted plans that later missed the validation bound, while "
        f"{words.get(tot['new_miss'], tot['new_miss'])} newly selected plan fell below it, at the cost of "
        f"{tot['adm'] - tot['adm_fw']} admissions and at most {f1(-min(changed_pts))} points of pooled service. "
        f"Screening a candidate took {1000 * med['20']['screen_median']:.0f} to "
        f"{1000 * med['200']['screen_median']:.0f}~ms, against seconds for generating it. Under four other delay "
        "models, the advantage of the capped procedures over conservative speed held for fixed plans. When the "
        "stored candidates were screened again under each model, the procedure with its stored fallback fell up to "
        f"{rescreen_macros.get('ResWorstDrop', '?')} points below the fixed plans, while with the best-screened "
        "fallback of "
        f"Section~\\ref{{sec:fallback}} it pooled between {rescreen_macros.get('ResLoOrt', '?')} and "
        f"{rescreen_macros.get('ResHiHgs', '?')}\\% (Appendix~\\ref{{sec:misspec}}).", ""]
    (ROOT / "paper/checks_summary.tex").write_text("\n".join(summary))
    print(json.dumps(macros, indent=1))


if __name__ == "__main__":
    main()
