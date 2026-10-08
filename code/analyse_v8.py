"""Generate the manuscript text, tables and macros for the confirmatory study
and the weight-sensitivity analysis from the retained records.

Reads results/confirm (stage-1 files, stage-2 records, analysis_output.txt),
results/weight_sensitivity and the archived development records in results/v7.
Writes paper/result_macros_v8.tex, paper/confirmatory_results.tex,
paper/weight_results.tex and paper/confirmatory_appendix.tex.

The confirmatory quantities are computed with the frozen analysis function and
must equal the saved output of the confirmatory run; the script stops if not.
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

import numpy as np

import confirm_analysis as ca

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "results" / "confirm"
WTS = ROOT / "results" / "weight_sensitivity"
VECTORS = {  # name -> (label, weights)
    "baseline_rerun": ("Original (rerun)", (0.5693, 0.2643, 0.1055, 0.0609)),
    "slack_first": ("Slack first", (0.2643, 0.5693, 0.1055, 0.0609)),
    "distance_heavy": ("Distance heavy", (0.80, 0.10, 0.05, 0.05)),
    "equal": ("Equal", (0.25, 0.25, 0.25, 0.25)),
}
SEED = 20260930
B = 20000


def f1(x):
    return f"{x:.1f}".replace("-", "$-$")


def f2(x):
    return f"{x:.2f}".replace("-", "$-$")


def boot(d, level=0.95):
    d = np.asarray(d, float)
    m = d[np.random.default_rng(SEED).integers(0, len(d), (B, len(d)))].mean(1)
    a = (1 - level) / 2 * 100
    return 100 * d.mean(), 100 * np.percentile(m, a), 100 * np.percentile(m, 100 - a)


def interval(m):
    return f"{f1(m[0])} [{f1(m[1])}, {f1(m[2])}]"


def table(caption, label, columns, header, rows, size="small", tabcolsep=None):
    pre = [] if tabcolsep is None else [f"\\setlength{{\\tabcolsep}}{{{tabcolsep}pt}}"]
    return "\n".join([r"\begin{table}[htbp]", r"\centering", f"\\{size}", *pre,
                      f"\\caption{{{caption}}}", f"\\label{{{label}}}",
                      f"\\begin{{tabular}}{{{columns}}}", r"\toprule", header + r"\\", r"\midrule",
                      *[row + r"\\" for row in rows], r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])


def confirmatory():
    stage1 = {}
    env = None
    for n in (20, 50, 100, 200):
        d = json.loads((CONF / f"study_v6_n{n}.json").read_text())
        env = env or d["environment"]
        assert not d.get("software_errors")
        for r in d["records"]:
            stage1[r["instance_seed"]] = r
    stage2 = {}
    for f in sorted(glob.glob(str(CONF / "v7" / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        stage2[r["instance_seed"]] = r
    units = [(s, n, stage2[s]) for n, seeds in ca.EXPECTED.items() for s in sorted(seeds)]
    out = ca.analyse(units, confirmatory=True)
    saved = json.loads((CONF / "analysis_output.txt").read_text())
    for key in ("H1_P_minus_C", "H2_K_minus_P", "H4_noise_growth"):
        for fld in ("mean_pp", "lo_pp", "hi_pp"):
            assert abs(out[key][fld] - saved[key][fld]) < 0.006, (key, fld)
        assert out[key]["verdict"] == saved[key]["verdict"]
    h3, s3 = out["H3_admission"], saved["H3_admission"]
    assert (h3["K_selected"], h3["P_selected"], h3["K_only"], h3["P_only"]) == \
        (s3["K_selected"], s3["P_selected"], s3["K_only"], s3["P_only"])
    assert abs(h3["exact_p"] - s3["exact_p"]) < 1e-5 and h3["verdict"] == s3["verdict"]
    no_plan = {c: sum(1 for r in stage2.values() if r["configuration_status"][c] != "ok")
               for c in ("conservative", "clock_aware", "nominal", "slack", "fleet_matched")}
    sel = {k: sum(v[k]["selected"] for v in out["descriptive_by_size"].values())
           for k in ("procedure", "screened_conservative", "capped_procedure")}
    ret = {k: sum(v[k]["retained"] for v in out["descriptive_by_size"].values())
           for k in ("procedure", "screened_conservative", "capped_procedure")}
    R = [stage2[s] for s in sorted(stage2)]
    val = lambda r, c: None if r["configurations"][c] is None else r["configurations"][c]["validation"]["service_level_success"]
    selP = lambda r: bool(r["old_failure_audit"]["selected"])
    selK = lambda r: r["capped_procedure"]["selected_plan"] is not None
    extra = {}
    for tag, chosen, c in (("P", selP, "procedure"), ("K", selK, "capped_procedure")):
        adm = [val(r, c) for r in R if chosen(r)]
        fb = [val(r, c) for r in R if not chosen(r)]
        alt = [val(r, c) if chosen(r) else (val(r, "conservative") if val(r, "conservative") is not None else val(r, c)) for r in R]
        extra[tag] = dict(adm=100 * float(np.mean(adm)), fb=100 * float(np.mean(fb)), nfb=len(fb),
                          posthoc=100 * float(np.mean(alt)),
                          changed=sum(1 for r in R if not chosen(r) and val(r, "conservative") is not None))
    d = lambda r: (val(r, "capped_procedure") or 0.0) - (val(r, "procedure") or 0.0)
    konly = [r for r in R if selK(r) and not selP(r)]
    neither = [r for r in R if not selK(r) and not selP(r)]
    assert all(abs(d(r)) < 1e-12 for r in neither), "procedures must share their fallback"
    extra["h2_from_konly"] = 100 * sum(d(r) for r in konly) / len(R)
    extra["n_konly"] = len(konly)
    return out, env, no_plan, sel, ret, extra


def weights():
    S = {}
    for f in glob.glob(str(WTS / "*.json")):
        r = json.loads(Path(f).read_text())
        S[(r["weights_name"], r["instance_seed"])] = r
    seeds = sorted({s for _, s in S})
    A = {s: json.loads((ROOT / f"results/v7/instance_{s}.json").read_text()) for s in seeds}
    assert len(S) == 4 * len(seeds) == 212
    P = lambda w, s: S[(w, s)]["procedure_service"]
    common = [s for s in seeds if A[s]["configurations"]["conservative"] is not None]
    cvals = {s: A[s]["configurations"]["conservative"]["validation"]["service_level_success"] for s in common}
    archived = {s: A[s]["configurations"]["procedure"]["validation"]["service_level_success"] for s in seeds}
    rows = {}
    for w in VECTORS:
        pc = boot([P(w, s) - cvals[s] for s in common])
        d = [P(w, s) - P("baseline_rerun", s) for s in seeds]
        diff = boot(d) if w != "baseline_rerun" else None
        diff_adj = boot(d, 1 - 0.05 / 3) if w != "baseline_rerun" else None
        only_w = sum(S[(w, s)]["selected"] and not S[("baseline_rerun", s)]["selected"] for s in seeds)
        only_o = sum(S[("baseline_rerun", s)]["selected"] and not S[(w, s)]["selected"] for s in seeds)
        n = only_w + only_o
        p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(only_w, only_o) + 1)) / 2 ** n) if n else 1.0
        rows[w] = dict(selected=sum(S[(w, s)]["selected"] for s in seeds),
                       pooled=100 * float(np.mean([P(w, s) for s in seeds])),
                       pc=pc, diff=diff, diff_adj=diff_adj, only_w=only_w, only_o=only_o, p=p,
                       identical=sum(abs(P(w, s) - P("baseline_rerun", s)) < 1e-9 for s in seeds))
    noise = boot([P("baseline_rerun", s) - archived[s] for s in seeds])
    archived_row = dict(selected=sum(bool(A[s]["old_failure_audit"]["selected"]) for s in seeds),
                        pooled=100 * float(np.mean(list(archived.values()))))
    return rows, noise, archived_row, len(common), len(seeds)


def names(lst):
    lst = list(lst)
    return lst[0] if len(lst) == 1 else ", ".join(lst[:-1]) + " and " + lst[-1]


def solomon():
    summ = json.loads((ROOT / "results" / "solomon_summary.json").read_text())
    hgs = json.loads((ROOT / "results" / "solomon_hgs_feasibility.json").read_text())
    order = ["R101", "R102", "R103", "R112", "RC104", "RC105", "RC106", "RC108"]
    assert sorted(summ) == sorted(order)
    plans = [k for k in order if summ[k]["nominal"] is not None]
    no_plan = [k for k in order if k not in plans]
    admitted = [k for k in plans if summ[k]["procedure_selected"]]
    fallback = [k for k in plans if not summ[k]["procedure_selected"]]
    cons_missing = [k for k in plans if summ[k]["conservative"] is None]
    assert all(summ[k]["capped"] == summ[k]["procedure"] for k in plans)
    assert all(summ[k]["capped_selected"] == summ[k]["procedure_selected"] for k in plans)
    hgs_nominal = [k for k in no_plan if hgs.get(k, {}).get("feasible") and hgs[k]["matrix"] == "nominal"]
    hgs_cons = [k for k in cons_missing if hgs.get(k, {}).get("feasible") and hgs[k]["matrix"] == "conservative-speed"]
    assert hgs_nominal == no_plan, "every missing nominal plan must be shown feasible by HGS"
    pct = lambda v: "--" if v is None else f"{v:.1f}"
    rows = []
    for k in order:
        v = summ[k]
        rows.append(f"{k} & {'yes' if k in plans else 'no'} & {pct(v['nominal'])} & {pct(v['conservative'])} & "
                    f"{pct(v['slack'])} & {pct(v['procedure'])} & {pct(v['capped'])} & "
                    f"{'yes' if v['procedure_selected'] else 'no'}")
    rng = lambda key, ks: f"{min(summ[k][key] for k in ks):.1f} to {max(summ[k][key] for k in ks):.1f}"
    cons_adm = [k for k in admitted if summ[k]["conservative"] is not None]
    low = [k for k in fallback if summ[k]["conservative"] is not None and summ[k]["procedure"] < summ[k]["conservative"]]
    fb_text = []
    for k in fallback:
        if summ[k]["conservative"] is None:
            fb_text.append(f"{k} ({summ[k]['procedure']:.1f}\\%; conservative speed returned no plan there, although HGS finds a "
                           f"feasible plan on its matrix)" if k in hgs_cons else
                           f"{k} ({summ[k]['procedure']:.1f}\\%; conservative speed returned no plan there)")
        else:
            gap = summ[k]["conservative"] - summ[k]["procedure"]
            fb_text.append(f"{k} ({summ[k]['procedure']:.1f}\\%), where it fell {gap:.1f} points below conservative speed "
                           f"({summ[k]['conservative']:.1f}\\%)" if gap > 0 else
                           f"{k} ({summ[k]['procedure']:.1f}\\%)")
    num = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
    tex = [
        r"\subsection{Solomon instances}\label{sec:solomon}", "",
        f"The unchanged pipeline was run on {num[len(order)]} 100-customer Solomon instances, with the study's "
        r"time-dependent profile and disturbance model added (Section~\ref{sec:confdesign}). Within its five-second budget, "
        f"OR-Tools returned a nominal plan for {num[len(plans)]} of the {num[len(order)]} instances (Table~\\ref{{tab:solomon}}). "
        f"PyVRP/HGS finds a feasible plan for the other {num[len(no_plan)]}, {names(no_plan)}, within "
        f"{int(hgs[no_plan[0]]['budget_s'])} seconds, so these failures are search limits of the generator, not "
        "infeasibility of the mapped instances. The failure policy records them as missing plans, and every configuration "
        "that depends on them as not attempted.", "",
        table("Solomon instances: validated service-event probability (\\%). A dash marks a configuration with no plan. "
              "\\emph{Plan} states whether OR-Tools returned a nominal plan; \\emph{Admitted} states whether screening admitted a plan "
              "for the original procedure, which otherwise returns the slack-aware fallback.",
              "tab:solomon", r"@{}lcccccccc@{}".replace("cccccccc", "ccccccc"),
              r"Instance & Plan & Nominal & Conservative & Slack-aware & Original & Capped & Admitted", rows),
        f"Of the {num[len(plans)]} instances with a plan, screening admitted a plan on {num[len(admitted)]} "
        f"({names(admitted)}). Their validated service probability was {rng('procedure', admitted)}\\%, against "
        f"{rng('conservative', cons_adm)}\\% for conservative speed and {rng('nominal', admitted)}\\% for nominal distance. "
        f"On the other {num[len(fallback)]}, the procedure returned the slack-aware fallback: " + " and ".join(fb_text) + ". "
        "Capping changed no result on any instance.", "",
        *[f"On {k}, screening admitted no plan, and the slack-aware fallback was weaker than the conservative plan. The "
          f"conservative-speed fallback examined post hoc in Section~\\ref{{sec:confirmatory}} would have returned "
          f"{summ[k]['conservative']:.1f}\\% there." for k in low], "",
        f"The {num[len(order)]} instances are all the R1 and RC1 files in the source repository. They give no basis for an "
        "interval estimate, and no Solomon comparison was prespecified. The admitted plans reached "
        f"{rng('procedure', admitted)}\\% and the fallback plans {rng('procedure', fallback)}\\%, a split similar to that on "
        "the synthetic instances. The generator, however, returned no plan on a substantial share of these harder instances.", "",
    ]
    (ROOT / "paper/solomon_results.tex").write_text("\n".join(tex))
    return {"SolomonN": str(len(order)), "SolomonPlans": str(len(plans)), "SolomonAdmitted": str(len(admitted)),
            "SolomonNoPlan": str(len(no_plan))}


def main():
    out, env, no_plan, sel, ret, extra = confirmatory()
    h1, h2, h3, h4 = out["H1_P_minus_C"], out["H2_K_minus_P"], out["H3_admission"], out["H4_noise_growth"]
    rows, noise, arch, k_common, n_inst = weights()
    verdict = lambda v: "confirmed" if v == "CONFIRMED" else "not confirmed"

    macros = {
        "ConfInstances": str(out["instances"]), "ConfCommon": str(out["common_subset"]),
        "ConfHOneMean": f1(h1["mean_pp"]), "ConfHOneLo": f1(h1["lo_pp"]), "ConfHOneHi": f1(h1["hi_pp"]),
        "ConfHTwoMean": f1(h2["mean_pp"]), "ConfHTwoLo": f1(h2["lo_pp"]), "ConfHTwoHi": f1(h2["hi_pp"]),
        "ConfHThreeK": str(h3["K_selected"]), "ConfHThreeP": str(h3["P_selected"]),
        "ConfHThreeKonly": str(h3["K_only"]), "ConfHThreePonly": str(h3["P_only"]),
        "ConfHThreeExact": f"{h3['exact_p']:.5f}".rstrip("0"),
        "ConfHFourMean": f1(h4["mean_pp"]), "ConfHFourLo": f1(h4["lo_pp"]), "ConfHFourHi": f1(h4["hi_pp"]),
        "ConfPooledP": f1(out["pooled_mean_pp"]["procedure"]),
        "ConfPooledSC": f1(out["pooled_mean_pp"]["screened_conservative"]),
        "ConfPooledK": f1(out["pooled_mean_pp"]["capped_procedure"]),
        "ConfRetainedP": f"{ret['procedure']}/{sel['procedure']}",
        "ConfRetainedK": f"{ret['capped_procedure']}/{sel['capped_procedure']}",
        "ConfNoPlanConservative": str(no_plan["conservative"]), "ConfNoPlanClock": str(no_plan["clock_aware"]),
        "ConfAdmMeanP": f1(extra["P"]["adm"]), "ConfFbMeanP": f1(extra["P"]["fb"]), "ConfFbCountP": str(extra["P"]["nfb"]),
        "ConfAdmMeanK": f1(extra["K"]["adm"]), "ConfFbMeanK": f1(extra["K"]["fb"]), "ConfFbCountK": str(extra["K"]["nfb"]),
        "PostHocP": f1(extra["P"]["posthoc"]), "PostHocK": f1(extra["K"]["posthoc"]),
        "PostHocChangedP": str(extra["P"]["changed"]), "PostHocChangedK": str(extra["K"]["changed"]),
        "HTwoFromKonly": f1(extra["h2_from_konly"]),
        "WtEqualDiffMean": f1(rows["equal"]["diff"][0]), "WtEqualDiffLo": f1(rows["equal"]["diff"][1]),
        "WtEqualDiffHi": f1(rows["equal"]["diff"][2]),
        "WtEqualPCMean": f1(rows["equal"]["pc"][0]), "WtEqualPCLo": f1(rows["equal"]["pc"][1]),
        "WtEqualPCHi": f1(rows["equal"]["pc"][2]),
        "WtEqualAdmitted": str(rows["equal"]["selected"]), "WtBaseAdmitted": str(rows["baseline_rerun"]["selected"]),
        "WtDistanceHeavyPCMean": f1(rows["distance_heavy"]["pc"][0]),
        "WtDistanceHeavyPCLo": f1(rows["distance_heavy"]["pc"][1]),
        "WtDistanceHeavyPCHi": f1(rows["distance_heavy"]["pc"][2]),
    }
    macros.update(solomon())
    (ROOT / "paper/result_macros_v8.tex").write_text(
        "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k, v in macros.items()) + "\n")

    # ---------------- confirmatory subsection ----------------
    hyp_rows = [
        r"H1 (primary) & Original procedure minus conservative speed, "
        f"{out['common_subset']} instances & {interval((h1['mean_pp'], h1['lo_pp'], h1['hi_pp']))} & 97.5\\% & {verdict(h1['verdict'])}",
        r"H2 (primary) & Capped minus original procedure, "
        f"{out['instances']} instances & {interval((h2['mean_pp'], h2['lo_pp'], h2['hi_pp']))} & 97.5\\% & {verdict(h2['verdict'])}",
        r"H3 & Admitted by capped / original procedure & "
        f"{h3['K_selected']} / {h3['P_selected']} (capped only {h3['K_only']}, original only {h3['P_only']}) & "
        f"exact $p={h3['exact_p']:.5f}$ & {verdict(h3['verdict'])}",
        r"H4 & Advantage at $\sigma=0.30$ minus at $\sigma=0.10$ ($\rho=0$), "
        f"{out['common_subset']} instances & {interval((h4['mean_pp'], h4['lo_pp'], h4['hi_pp']))} & 95\\% & {verdict(h4['verdict'])}",
    ]
    conf_tex = [
        r"\subsection{First confirmatory study}\label{sec:confirmatory}", "",
        r"The four hypotheses of the prespecified protocol were tested on "
        f"{out['instances']} new instances (Table~\\ref{{tab:confirmatory}}). Every decision uses the "
        r"unrounded interval limits, and the protocol's validation checks passed before any quantity was computed.",
        "",
        table("First confirmatory study on 53 new instances. Differences are in percentage points of validated "
              "service-event probability; intervals are paired bootstrap intervals over instances. "
              "Conservative speed returned a plan on " + str(out['common_subset']) + " of " + str(out['instances']) +
              " instances, and H1 and H4 use those instances, as the protocol specifies.",
              "tab:confirmatory", r"@{}>{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{4.2cm}>{\raggedright\arraybackslash}p{3.5cm}cc@{}",
              r"Hypothesis & Quantity & Estimate [interval] & Level & Decision", hyp_rows, size="footnotesize"),
        f"All four hypotheses were confirmed. The original procedure exceeded conservative speed by "
        f"{f1(h1['mean_pp'])} points, and capping added {f1(h2['mean_pp'])} points. "
        f"Capping admitted {h3['K_selected']} instances against {h3['P_selected']} and lost none that the "
        f"original procedure admitted ({h3['K_only']} gained, {h3['P_only']} lost). For independent disturbances, the advantage "
        f"over conservative speed was {f1(h4['mean_pp'])} points larger at $\\sigma=0.30$ than at $\\sigma=0.10$. "
        f"Of the plans admitted on the screening bank, {ret['procedure']} of {sel['procedure']} (original) and "
        f"{ret['capped_procedure']} of {sel['capped_procedure']} (capped) kept the 0.95 lower bound on the fresh bank.",
        "",
        f"Averaged over all instances, service probability was {f1(out['pooled_mean_pp']['procedure'])}\\% for the original "
        f"procedure, {f1(out['pooled_mean_pp']['screened_conservative'])}\\% for screened conservative speed and "
        f"{f1(out['pooled_mean_pp']['capped_procedure'])}\\% for the capped procedure, so on average the 95\\% target is "
        f"still not met. Screened conservative speed was not a prespecified comparison, and its value is descriptive only. "
        f"As in the development study, the shortfall comes from instances without an admitted plan. Plans admitted by "
        f"screening averaged {f1(extra['P']['adm'])}\\% for the original procedure and {f1(extra['K']['adm'])}\\% for the capped "
        f"procedure, while the fallback plans averaged {f1(extra['P']['fb'])}\\% ({extra['P']['nfb']} instances) and "
        f"{f1(extra['K']['fb'])}\\% ({extra['K']['nfb']} instances).",
        "",
        f"H2 and H3 are not independent. When neither procedure admits a plan, both return the same fallback, and "
        f"{f1(extra['h2_from_konly'])} of the {f1(h2['mean_pp'])} points of H2 come from the {extra['n_konly']} instances that only "
        f"the capped procedure admits. The two hypotheses measure one finding twice.",
        "",
        f"\\paragraph{{Post hoc fallback.}} The protocol fixes the fallback: when no plan is admitted, both procedures return "
        f"the uncontracted slack-aware plan. Returning the conservative-speed plan instead, where that plan "
        f"exists, would have raised pooled service on the same fresh bank from {f1(out['pooled_mean_pp']['procedure'])}\\% to "
        f"{f1(extra['P']['posthoc'])}\\% for the original procedure ({extra['P']['changed']} instances changed) and from "
        f"{f1(out['pooled_mean_pp']['capped_procedure'])}\\% to {f1(extra['K']['posthoc'])}\\% for the capped procedure "
        f"({extra['K']['changed']} instances changed). This rule uses no validation outcome, but it was "
        f"chosen after the results were seen, so the comparison is exploratory. The second confirmatory study tests it "
        f"prospectively (Section~\\ref{{sec:confirmatory2}}).",
        "",
        "These instances come from the same generator and the same assumed disturbance model as the development study, "
        "so the result shows repeatability within that setting. It says nothing about real road networks, calibrated "
        "parameters or other instance families.",
        "",
    ]
    (ROOT / "paper/confirmatory_results.tex").write_text("\n".join(conf_tex))

    size_rows = []
    for n in ("20", "50", "100", "200"):
        v = out["descriptive_by_size"][n]
        cell = lambda k: f"{v[k]['selected']}/{v['instances']} ({v[k]['retained']}) & {f1(v[k]['mean_pp'])}"
        size_rows.append(f"{n} & {v['instances']} & {cell('procedure')} & {cell('screened_conservative')} & {cell('capped_procedure')}")
    (ROOT / "paper/confirmatory_appendix.tex").write_text("\n".join([
        table("First confirmatory study by size (descriptive). For each procedure: the number of instances admitted by "
              "screening, with the number that kept the 0.95 lower bound on the fresh bank in parentheses, "
              "and the mean validated service-event probability (\\%) over all instances, including fallbacks.",
              "tab:conf-size", r"@{}rrrrrrrr@{}",
              r"$n$ & Inst. & \multicolumn{2}{c}{Original} & \multicolumn{2}{c}{Screened conservative} & \multicolumn{2}{c}{Capped}",
              size_rows, size="footnotesize")]))

    # ---------------- weight sensitivity subsection ----------------
    wrows = []
    for w, (label, wt) in VECTORS.items():
        r = rows[w]
        d = "--" if r["diff"] is None else interval(r["diff"])
        wrows.append(f"{label} & ({', '.join(f'{x:g}' for x in wt)}) & {r['selected']} & {f1(r['pooled'])} & "
                     f"{interval(r['pc'])} & {d}")
    wt_tex = [
        r"\subsection{Sensitivity to the objective weights}\label{sec:weights}", "",
        f"The original procedure was rerun on the {n_inst} development instances with four weight vectors "
        r"(Table~\ref{tab:weights}); neither confirmatory study varied the weights. Each rerun regenerates the "
        "candidate family, screens it on the same bank and validates the selected plan or fallback on the same fresh bank. "
        "Conservative-speed planning does not use the weights, so its archived outcome is reused. "
        f"The rerun with the original weights differs from the archived run by {f1(noise[0])} points pooled "
        f"([{f1(noise[1])}, {f1(noise[2])}]) and by one admitted instance ({rows['baseline_rerun']['selected']} against "
        f"{arch['selected']}). This is the run-to-run variation of a time-limited search.",
        "",
        table("Weight sensitivity on the " + str(n_inst) + " development instances. Weights are ordered distance cost, slack deficit, "
              "driver duration, fleet use. The advantage over conservative speed uses the " + str(k_common) + " instances where "
              "conservative speed returned a plan. The last column is the paired difference in service probability from the "
              "rerun with the original weights, over all 53 instances (percentage points).",
              "tab:weights", r"@{}>{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{4.4cm}>{\raggedright\arraybackslash}p{1.4cm}>{\raggedright\arraybackslash}p{1.3cm}>{\raggedright\arraybackslash}p{2.5cm}>{\raggedright\arraybackslash}p{2.5cm}@{}",
              r"Vector & Weights & Admitted & Pooled (\%) & Advantage over conservative [95\%] & Paired difference [95\%]",
              wrows, size="footnotesize", tabcolsep=3),
        f"Swapping the two largest weights changed nothing beyond the run-to-run variation. The distance-heavy vector "
        f"gave pooled service {f1(abs(rows['distance_heavy']['diff'][0]))} points lower, with a paired interval that includes "
        f"zero, and its advantage over conservative speed stayed clearly positive "
        f"({interval(rows['distance_heavy']['pc'])}). Equal weights changed the most. They admitted "
        f"{rows['equal']['selected']} instances against {rows['baseline_rerun']['selected']}, lowered pooled service by "
        f"{f1(abs(rows['equal']['diff'][0]))} points (paired interval {interval(rows['equal']['diff'])}; "
        f"{f1(rows['equal']['diff_adj'][1])} to {f1(rows['equal']['diff_adj'][2])} after adjusting the level for three "
        f"comparisons), and left an advantage over conservative speed whose interval includes zero "
        f"({interval(rows['equal']['pc'])}). Of the instances whose admission differed, {rows['equal']['only_o']} were admitted "
        f"only under the original weights and {rows['equal']['only_w']} only under equal weights (exact $p={rows['equal']['p']:.3f}$, unadjusted; the "
        f"adjusted threshold for three comparisons is 0.017).",
        "",
        "This analysis is exploratory. It uses the development instances and four vectors, chosen without searching for the "
        "point at which the advantage disappears, and each vector was run once. The records do not store route structure, so "
        "the reason equal weights do worse is not tested here. Equal weights give fleet size and driver duration "
        "0.25 each, against 0.06 and 0.11 in the original vector.",
        "",
    ]
    (ROOT / "paper/weight_results.tex").write_text("\n".join(wt_tex))
    print(json.dumps({"macros": macros}, indent=1)[:2500])


if __name__ == "__main__":
    main()
