"""Manuscript text, tables and macros for the revision-3 analyses.

Sections written (each only when its records exist):
  paper/fallback_results.tex     post hoc fallback rules (results/fallback_policy.json) and, when
                                 present, part B of protocol 3 (results/confirm3_fallback_analysis_output.json)
  paper/robust_extra.tex         fleet-matched robust contrast (results/robust_fleet_matched.json),
                                 robust plans with 200 customers (results/robust_capped_dev200) and, when
                                 present, part A of protocol 3 (results/confirm_robust_analysis_output.json)
  paper/weight_bracketing.tex    weight bracketing (results/weight_bracketing)
  paper/gh_results.tex           Gehring-Homberger check (results/gh200_summary.json)
  paper/result_macros_v12.tex    macros used in the abstract, introduction and conclusion
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

from analyse_robust import boot, screened_robust

ROOT = Path(__file__).resolve().parents[1]
MACROS: dict[str, str] = {}


def f1(x):
    return f"{x:.1f}".replace("-", "$-$")


def f2(x):
    return f"{x:.2f}".replace("-", "$-$")


def iv(m):
    return f"{f1(m[0])} [{f1(m[1])}, {f1(m[2])}]"


def tab(caption, label, cols, header, rows, size="footnotesize"):
    return "\n".join([r"\begin{table}[htbp]", r"\centering", f"\\{size}", r"\setlength{\tabcolsep}{4pt}",
                      f"\\caption{{{caption}}}", f"\\label{{{label}}}", f"\\begin{{tabular}}{{{cols}}}", r"\toprule",
                      header + r"\\", r"\midrule", *[r + r"\\" for r in rows], r"\bottomrule", r"\end{tabular}",
                      r"\end{table}", ""])


def load_json(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


# --------------------------------------------------------------------------- fallback
def fallback_section():
    fp = load_json("results/fallback_policy.json")
    names = {"original": "Original (OR-Tools)", "capped": "Capped (OR-Tools)",
             "hgs_capped": "HGS capped"}
    rows, gains, capped_pooled, fb_best, fb_stored = [], [], [], [], []
    for study, procs in fp["studies"].items():
        for proc, v in procs.items():
            s = v["summary"]
            d = s["minus_stored"]["best_screen"]
            rows.append(f"{study.capitalize()} & {names[proc]} & {s['fallback_instances']} & {f1(s['pooled']['stored'])} & "
                        f"{f1(s['pooled']['conservative'])} & {f1(s['pooled']['best_screen'])} & {iv(d)}")
            gains.append(d)
            if proc != "original":
                capped_pooled.append(s["pooled"]["best_screen"])
            if s["fallback_instances"]:
                fb_best.append(s["fallback_mean"]["best_screen"])
                fb_stored.append(s["fallback_mean"]["stored"])
    assert all(g[1] > 0 for g in gains), "every gain interval above zero is stated in the text"
    MACROS.update({"FbGainMin": f1(min(g[0] for g in gains)), "FbGainMax": f1(max(g[0] for g in gains)),
                   "FbCappedPooledMin": f1(min(capped_pooled)), "FbCappedPooledMax": f1(max(capped_pooled))})
    text = [
        r"\subsection{Fallback rule}\label{sec:fallback}", "",
        "When screening admits no candidate, each procedure returns a fixed fallback: the uncontracted slack-aware "
        "plan for the OR-Tools procedures and the conservative-speed plan for the HGS procedure. These fallbacks are "
        "the main reason the procedures pool below the 95\\% target. After the development study and both "
        "confirmatory studies, a third fallback rule was examined: return the candidate of the procedure's own family with the highest screening success "
        "(ties by the normalized score, then the smaller buffer). The rule uses only the screening evidence already "
        "computed, so the validation bank still judges the returned plan independently, and it changes nothing on "
        f"instances where a plan was admitted. Table~\\ref{{tab:fallback}} compares the rules on the stored records "
        "(\\texttt{code/fallback\\_policy.py}).", "",
        tab("Fallback rules on the stored records (exploratory, post hoc): instances where screening admitted "
            "nothing, pooled validated service-event probability (\\%) over all instances under the stored fallback, "
            "the conservative-speed plan and the best-screened candidate, and the paired difference best-screened "
            "minus stored with a 95\\% bootstrap interval (percentage points).",
            "tab:fallback", r"@{}ll>{\raggedleft\arraybackslash}p{1.2cm}rrrl@{}",
            r"Study & Procedure & Fallback inst. & Stored & Cons. & Best & Best minus stored", rows),
        "The best-screened rule raised pooled service for every study and procedure, by "
        f"{f1(min(g[0] for g in gains))} to {f1(max(g[0] for g in gains))} points, and every interval lies above "
        f"zero. With it the capped procedures pooled {f1(min(capped_pooled))} to {f1(max(capped_pooled))}\\%. On "
        f"the fallback instances themselves its plans averaged {f1(min(fb_best))} to {f1(max(fb_best))}\\%, against "
        f"{f1(min(fb_stored))} to {f1(max(fb_stored))}\\% for the stored fallbacks. The conservative-speed fallback "
        "helped less. Because the rule was chosen after these results were known, part B of the third protocol "
        "tested it on new instances.", "",
    ]
    out = load_json("results/confirm3_fallback_analysis_output.json")
    if out:
        text += part_b(out)
    (ROOT / "paper/fallback_results.tex").write_text("\n".join(text))


def part_b(out):
    v = lambda k: (out[k]["mean"], out[k]["lo"], out[k]["hi"])
    rows = [f"F1 (primary) & OR-Tools capped, best-screened minus slack-aware fallback & {iv(v('F1'))} & 97.5\\% & "
            f"{out['F1']['verdict'].lower()}",
            f"F2 (primary) & HGS capped, best-screened minus conservative fallback & {iv(v('F2'))} & 97.5\\% & "
            f"{out['F2']['verdict'].lower()}",
            f"F3 (estimate) & Pooled service, OR-Tools capped with best-screened fallback & {iv(v('F3'))} & 95\\% & --",
            f"F4 (estimate) & Pooled service, HGS capped with best-screened fallback & {iv(v('F4'))} & 95\\% & --"]
    MACROS.update({"PbFOne": f1(out["F1"]["mean"]), "PbFOneLo": f1(out["F1"]["lo"]), "PbFOneHi": f1(out["F1"]["hi"]),
                   "PbFTwo": f1(out["F2"]["mean"]), "PbFTwoLo": f1(out["F2"]["lo"]), "PbFTwoHi": f1(out["F2"]["hi"]),
                   "PbFThree": f1(out["F3"]["mean"]), "PbFThreeLo": f1(out["F3"]["lo"]), "PbFThreeHi": f1(out["F3"]["hi"]),
                   "PbFFour": f1(out["F4"]["mean"]), "PbFFourLo": f1(out["F4"]["lo"]), "PbFFourHi": f1(out["F4"]["hi"]),
                   "PbInstances": str(out["instances"]),
                   "PbOrtFallbacks": str(out["fallback_instances"]["ort"]),
                   "PbHgsFallbacks": str(out["fallback_instances"]["hgs"]),
                   "PbOrtPooled": f1(out["pooled"]["ort_capped"]), "PbHgsPooled": f1(out["pooled"]["hgs_capped_cons"])})
    # descriptive: instances on which the OR-Tools anchor solves found no plan, so neither procedure ran
    import confirm_analysis_fallback as caf
    stage1 = caf.stage1_records([ROOT / p for p in caf.PART_B["stage1"]])
    units = caf.units_for(stage1, caf.load(caf.PART_B["stage2"]), caf.load(caf.PART_B["hgs"]))
    no_anchor = [u for u in units if stage1[u["seed"]]["reference_ranges"] is None]
    rest = [u for u in units if stage1[u["seed"]]["reference_ranges"] is not None]
    for u in no_anchor:
        assert u["ort_capped_best"] == 0 and u["hgs_capped_best"] == 0
    ex_ort = float(np.mean([u["ort_capped_best"] for u in rest]))
    ex_hgs = float(np.mean([u["hgs_capped_best"] for u in rest]))
    MACROS.update({"PbNoAnchor": str(len(no_anchor)), "PbExOrt": f1(ex_ort), "PbExHgs": f1(ex_hgs)})
    assert out["F1"]["verdict"] == "CONFIRMED" and out["F2"]["verdict"] == "CONFIRMED"
    return [
        "Part B ran the frozen OR-Tools and HGS pipelines on "
        f"{out['instances']} new instances (development seeds plus 120000) under the third protocol "
        "\\cite{ali2026freeze3}. Table~\\ref{tab:partb} gives the prespecified results.", "",
        tab("Third protocol, part B: prespecified results on the new instances. Differences and pooled service are "
            "in percentage points and percent; intervals are paired bootstrap intervals over instances.",
            "tab:partb", r"@{}l>{\raggedright\arraybackslash}p{5.6cm}lll@{}",
            r"Hypothesis & Quantity & Mean [interval] & Level & Decision", rows),
        f"Screening admitted nothing on {out['fallback_instances']['ort']} instances for the OR-Tools capped "
        f"procedure and on {out['fallback_instances']['hgs']} for the HGS capped procedure. With their stored "
        f"fallbacks the two procedures pooled {f1(out['pooled']['ort_capped'])}\\% and "
        f"{f1(out['pooled']['hgs_capped_cons'])}\\%; with the best-screened fallback they pooled "
        f"{f1(out['pooled']['ort_capped_best'])}\\% and {f1(out['pooled']['hgs_capped_best'])}\\%. Both "
        "primary hypotheses met their decision criteria. The pooled estimates stay just below 95\\%. "
        f"{'One instance' if len(no_anchor) == 1 else f'{len(no_anchor)} instances'} cost more than the whole "
        "shortfall: "
        "there the OR-Tools anchor solves that fix the scaling ranges found no plan, so neither procedure could run "
        "and the instance scores zero, as the failure policy requires. On the other "
        f"{len(rest)} instances the two procedures with the best-screened fallback pooled {f1(ex_ort)}\\% and "
        f"{f1(ex_hgs)}\\%; these figures are descriptive and were not prespecified. Both halves ran on a two-core "
        "Linux machine (Section~\\ref{sec:conf3design}). The first stage was interrupted once by a restart of that "
        "machine; the frozen drivers resume from the records already written, so the completed instances were kept "
        "and the rest were run afterwards.", "",
    ]


# --------------------------------------------------------------------------- robust additions
def robust_extra():
    fm = load_json("results/robust_fleet_matched.json")
    text = robust_200()
    out = load_json("results/confirm_robust_analysis_output.json")
    if out:
        text += part_a(out)
    dev, conf = fm["development"], fm.get("confirmatory")
    for d in (dev, conf):
        if d is None:
            continue
        for k in ("hgs_capped_cons", "ort_capped"):
            assert d[k]["service_matched_minus_ref"][1] < 0 < d[k]["service_matched_minus_ref"][2], k
    h, o = dev["hgs_capped_cons"], dev["ort_capped"]
    MACROS.update({"FmHgs": f1(h["service_matched_minus_ref"][0]), "FmHgsLo": f1(h["service_matched_minus_ref"][1]),
                   "FmHgsHi": f1(h["service_matched_minus_ref"][2])})
    para = ("Restricting the robust plans to the comparator's fleet removed much of their advantage. For each "
            "instance, the relieved settings were limited to plans that use no more vehicles than the comparator's "
            "plan, and the screened-robust rule was applied within that limit "
            "(\\texttt{code/robust\\_fleet\\_matched.py}; exploratory, not part of the protocol). The limit also "
            "removes the most protective settings on many instances, so the comparison is not a pure fleet "
            "effect. On the development instances the restricted plans differed from the HGS capped procedure by "
            f"{iv(h['service_matched_minus_ref'])} points in service, with "
            f"{f1(-h['distance_matched_vs_ref_pct'][0])}\\% less distance, and from the OR-Tools capped procedure "
            f"by {iv(o['service_matched_minus_ref'])} points on the {o['with_fleet_matched_plan']} instances with "
            f"such a plan; screening admitted a restricted plan on {h['admitted_within_fleet']} and "
            f"{o['admitted_within_fleet']} instances.")
    if conf:
        hc, oc = conf["hgs_capped_cons"], conf["ort_capped"]
        MACROS.update({"FmConfHgs": f1(hc["service_matched_minus_ref"][0]),
                       "FmConfHgsLo": f1(hc["service_matched_minus_ref"][1]),
                       "FmConfHgsHi": f1(hc["service_matched_minus_ref"][2]),
                       "FmConfOrt": f1(oc["service_matched_minus_ref"][0]),
                       "FmConfOrtLo": f1(oc["service_matched_minus_ref"][1]),
                       "FmConfOrtHi": f1(oc["service_matched_minus_ref"][2])})
        para += (" On the confirmatory instances of part A the differences were "
                 f"{iv(hc['service_matched_minus_ref'])} points against the HGS capped procedure "
                 f"({hc['with_fleet_matched_plan']} instances, {hc['admitted_within_fleet']} admitted) and "
                 f"{iv(oc['service_matched_minus_ref'])} against the OR-Tools capped procedure "
                 f"({oc['with_fleet_matched_plan']} instances, {oc['admitted_within_fleet']} admitted).")
    para += (" Every interval includes zero, so with no larger fleet than the comparator the robust plans were not "
             "measurably more reliable.")
    text += [para, ""]
    (ROOT / "paper/robust_extra.tex").write_text("\n".join(text))


def robust_200():
    files = sorted(glob.glob(str(ROOT / "results/robust_capped_dev200/instance_*.json")))
    if len(files) < 8:
        return []
    recs = [json.loads(Path(f).read_text()) for f in files]
    hgs = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
           for f in glob.glob(str(ROOT / "results/hgs_dev/instance_9*.json"))}
    ort = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
           for f in glob.glob(str(ROOT / "results/v7/instance_9*.json"))}
    sv = lambda e: 0.0 if e is None or e.get("validation") is None else 100 * e["validation"]["service_level_success"]
    keys = recs[0]["grid"]
    pooled = {k: float(np.mean([sv(r["settings"][k]) for r in recs])) for k in keys}
    plans = {k: sum(r["settings"][k]["status"] == "ok" for r in recs) for k in keys}
    scr = [screened_robust(r["settings"]) for r in recs]
    scr_p = float(np.mean([sv(x[0]) for x in scr]))
    hg = float(np.mean([sv(hgs[r["instance_seed"]]["configurations"]["hgs_capped_cons"]) for r in recs]))
    og = float(np.mean([sv(ort[r["instance_seed"]]["configurations"]["capped_procedure"]) for r in recs]))
    secs = float(np.median([e["solve_seconds"] for r in recs for e in r["settings"].values()]))
    fl = lambda e: e["plan"]["metrics"]["fleet"]
    scr_f = float(np.mean([fl(x[0]) for x in scr]))
    hg_f = float(np.mean([fl(hgs[r["instance_seed"]]["configurations"]["hgs_capped_cons"]) for r in recs]))
    og_f = float(np.mean([fl(ort[r["instance_seed"]]["configurations"]["capped_procedure"]) for r in recs]))
    missing = len(recs) - min(plans[k] for k in ("G3_d0.6", "box_d0.6"))
    assert all(plans[k] == len(recs) for k in ("G3_d0.4", "box_d0.4"))
    return [
        f"With 200 customers, the relieved model was run on the {len(recs)} development instances with a reduced "
        f"grid: $\\Gamma=3$ and box uncertainty, each at $\\theta=0.4$ and $0.6$, with 2000 iterations (median "
        f"{secs:.0f}~s per solve). At $\\theta=0.4$ the two budgets pooled {f1(pooled['G3_d0.4'])}\\% and "
        f"{f1(pooled['box_d0.4'])}\\%. At $\\theta=0.6$ they pooled {f1(pooled['G3_d0.6'])}\\% and "
        f"{f1(pooled['box_d0.6'])}\\%, because the search found no plan for "
        f"{'one instance' if missing == 1 else f'{missing} instances'} under either budget; at this size relief "
        "does not guarantee a plan, and the search alone does not show whether that model is infeasible. Screened "
        f"robust over the four settings admitted a plan on {sum(x[1] for x in scr)} instances and pooled "
        f"{f1(scr_p)}\\% with {f1(scr_f)} vehicles on average, against {f1(hg)}\\% with {f1(hg_f)} vehicles for the "
        f"HGS capped procedure and {f1(og)}\\% with {f1(og_f)} for the OR-Tools capped procedure on the same "
        "instances. With eight instances these figures are descriptive only.", "",
    ]


def part_a(out):
    v = lambda k: (out[k]["mean"], out[k]["lo"], out[k]["hi"])
    rows = [f"R1 (primary) & Screened robust with relief minus OR-Tools capped, service & {iv(v('R1'))} & 97.5\\% & "
            f"{out['R1']['verdict'].lower()}",
            f"R2 (primary) & Screened robust with relief minus HGS capped, service & {iv(v('R2'))} & 97.5\\% & "
            f"{out['R2']['verdict'].lower()}",
            f"R3 & Screened robust with relief minus HGS capped, vehicles & {f2(out['R3']['mean'])} "
            f"[{f2(out['R3']['lo'])}, {f2(out['R3']['hi'])}] & 95\\% & {out['R3']['verdict'].lower()}",
            f"R4 & Screened robust with relief vs. relief box $\\theta=0.6$, distance (\\%) & {iv(v('R4'))} & 95\\% & "
            f"{out['R4']['verdict'].lower()}"]
    MACROS.update({"PaROne": f1(out["R1"]["mean"]), "PaROneLo": f1(out["R1"]["lo"]), "PaROneHi": f1(out["R1"]["hi"]),
                   "PaRTwo": f1(out["R2"]["mean"]), "PaRTwoLo": f1(out["R2"]["lo"]), "PaRTwoHi": f1(out["R2"]["hi"]),
                   "PaRThree": f2(out["R3"]["mean"]), "PaRFour": f1(out["R4"]["mean"]),
                   "PaRFourAbs": f1(-out["R4"]["mean"]), "PaBoxMinusScr": f1(out["service_box_0.6_minus_screened"]["mean"]),
                   "PaInstances": str(out["instances"]), "PaScreenedP": f1(out["pooled"]["screened_relief"]),
                   "PaOrtP": f1(out["pooled"]["ort_capped"]), "PaHgsP": f1(out["pooled"]["hgs_capped_cons (study 2)"]),
                   "PaBoxP": f1(out["pooled"]["relief_box_0.6"]), "PaAdmitted": str(out["screened_admitted"])})
    return [
        r"\subsection{Robust comparison on the confirmatory instances}\label{sec:parta}", "",
        "Part A of the third protocol \\cite{ali2026freeze3} tested the development findings on the "
        f"{out['instances']} confirmatory instances with up to 100 customers. Table~\\ref{{tab:parta}} gives the "
        "prespecified results.", "",
        tab("Third protocol, part A: prespecified results on the confirmatory instances with up to 100 customers. "
            "R1 and R4 use all instances of both studies; R2 and R3 use the second study, where HGS plans exist.",
            "tab:parta", r"@{}l>{\raggedright\arraybackslash}p{5.6cm}lll@{}",
            r"Hypothesis & Quantity & Mean [interval] & Level & Decision", rows),
        ("All four hypotheses met their decision criteria. " if all(out[h]["verdict"] == "CONFIRMED"
                                                                    for h in ("R1", "R2", "R3", "R4")) else "")
        + f"Screened robust with relief pooled {f1(out['pooled']['screened_relief'])}\\%, against "
        f"{f1(out['pooled']['ort_capped'])}\\% for the OR-Tools capped procedure and "
        f"{f1(out['pooled']['relief_box_0.6'])}\\% for the most protective relieved setting; on the second "
        f"study the HGS capped procedure pooled {f1(out['pooled']['hgs_capped_cons (study 2)'])}\\%. Screening "
        f"admitted a robust plan on {out['screened_admitted']} of {out['instances']} instances.", "",
    ]


# --------------------------------------------------------------------------- weight bracketing
def weight_bracketing():
    files = glob.glob(str(ROOT / "results/weight_bracketing/*.json"))
    recs = [json.loads(Path(f).read_text()) for f in files]
    names = ("original_here", "equal_here", "fleet_up", "duration_up")
    by = {n: {r["instance_seed"]: r for r in recs if r["weights_name"] == n} for n in names}
    if any(len(by[n]) < 53 for n in names):
        return False
    archived = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
                for f in glob.glob(str(ROOT / "results/v7/instance_*.json"))}
    cons = {s: archived[s]["configurations"]["conservative"] for s in archived}
    rows, stats = [], {}
    label = {"original_here": "Original (rerun here)", "equal_here": "Equal (rerun here)",
             "fleet_up": "Fleet weight raised", "duration_up": "Duration weight raised"}
    for n in names:
        rs = by[n]
        common = [s for s in rs if cons[s] is not None]
        adv = boot([100 * ((rs[s]["procedure_service"] or 0) - cons[s]["validation"]["service_level_success"]) for s in common])
        diff = boot([100 * ((rs[s]["procedure_service"] or 0) - (by["original_here"][s]["procedure_service"] or 0))
                     for s in rs]) if n != "original_here" else None
        # planned fleet and candidate screening success
        fleet = lambda r: None if r["plan"] is None else r["plan"]["metrics"]["fleet"]
        adm = sum(r["selected"] for r in rs.values())
        cand_pass = np.mean([np.mean([c["screening_lcb"] >= 0.95 for c in r["candidates"] if c["screening_lcb"] is not None] or [0])
                             for r in rs.values()])
        cand_fleet = np.mean([np.mean([c["metrics"]["fleet"] for c in r["candidates"] if c["metrics"]] or [np.nan])
                              for r in rs.values()])
        w = next(iter(rs.values()))["weights"]
        stats[n] = {"adm": adm, "adv": adv, "diff": diff, "pass": 100 * cand_pass, "fleet": cand_fleet,
                    "pooled": float(np.mean([100 * (r["procedure_service"] or 0) for r in rs.values()]))}
        rows.append(f"{label[n]} & ({', '.join(f'{x:g}' for x in w)}) & {adm} & {f1(stats[n]['pooled'])} & {iv(adv)} & "
                    f"{'--' if diff is None else iv(diff)} & {f1(stats[n]['pass'])} & {f2(cand_fleet)}")
    (ROOT / "paper/weight_bracketing.tex").write_text("\n".join([
        "To find what breaks under equal weights, two further vectors were fixed before a new run on the same "
        "instances: the original vector with the fleet-use weight raised to 0.25, and the original vector with the "
        "driver-duration weight raised to 0.25, the other weights scaled in proportion "
        "(\\texttt{code/weight\\_bracketing.py}). Equal weights change both at once. The original and equal "
        "vectors were rerun on the same machine, so the four rows of Table~\\ref{tab:bracket} are comparable with "
        "each other; the run also stored every candidate, which the earlier run did not.", "",
        tab("Weight bracketing on the 53 development instances (exploratory). Advantage over conservative speed on "
            "the instances where it has a plan, paired difference in service from the original vector rerun on the "
            "same machine (percentage points), and, averaged over instances, the share of candidates whose screening "
            "lower bound reached 0.95 and the mean vehicles per candidate.",
            "tab:bracket", r"@{}l>{\raggedright\arraybackslash}p{2.9cm}rrllrr@{}",
            r"Vector & Weights & Adm. & Pooled & Advantage [95\%] & Diff.\ from original & Pass (\%) & Veh.",
            rows, size="scriptsize"),
        bracket_text(stats, by), ""]))
    json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in stats.items()},
              open(ROOT / "results/weight_bracketing_summary.json", "w"), indent=1, default=float)
    return True


def bracket_text(st, by):
    o, e, fu, du = (st[k] for k in ("original_here", "equal_here", "fleet_up", "duration_up"))
    # paired candidate-level differences from the original vector (same instance and buffer)
    def paired(name, metric):
        d = []
        for seed, r in by[name].items():
            oc = {c["beta"]: c for c in by["original_here"][seed]["candidates"] if c["metrics"]}
            for c in r["candidates"]:
                if c["metrics"] and c["beta"] in oc:
                    d.append(metric(c) - metric(oc[c["beta"]]))
        return float(np.mean(d))
    fleet = lambda c: c["metrics"]["fleet"]
    succ = lambda c: 100 * c["screening_success"]
    dur = lambda c: c["metrics"]["driver_duration"]
    tight = lambda c: c["metrics"]["tightness"]
    pf = {n: paired(n, fleet) for n in ("equal_here", "fleet_up", "duration_up")}
    ps = {n: paired(n, succ) for n in ("equal_here", "fleet_up", "duration_up")}
    pt = paired("duration_up", tight)
    pdur = paired("duration_up", dur)
    # the sentences rely on these patterns
    assert du["diff"][0] < fu["diff"][0] < 0 and du["diff"][2] < 0 and fu["diff"][2] < 0
    assert abs(du["diff"][0] - e["diff"][0]) < 1.0
    assert e["adv"][0] < 0.5 * o["adv"][0]
    earlier = load_json("results/weight_sensitivity_summary.json")      # the earlier run, other machine
    assert earlier["equal"]["P_minus_C_pp"][0] < 0.5 * earlier["baseline_rerun"]["P_minus_C_pp"][0]
    assert ps["duration_up"] < ps["fleet_up"] < 0 and pf["duration_up"] > pf["fleet_up"]
    assert pt > 0 and pdur < 0
    dvf = boot([100 * ((by["duration_up"][k]["procedure_service"] or 0) - (by["fleet_up"][k]["procedure_service"] or 0))
                for k in by["duration_up"]])
    assert dvf[1] < 0 < dvf[2]
    MACROS.update({"BrOrigAdv": f1(o["adv"][0]), "BrEqAdv": f1(e["adv"][0]), "BrEqAdvLo": f1(e["adv"][1]),
                   "BrEqAdvHi": f1(e["adv"][2]), "BrDurDiff": f1(du["diff"][0]), "BrFleetDiff": f1(fu["diff"][0]),
                   "BrEqDiff": f1(e["diff"][0])})
    return (
        f"Rerun on the same machine, the original vector admitted {o['adm']} instances and the equal vector "
        f"{e['adm']}, and the advantage over conservative speed fell from {iv(o['adv'])} to {iv(e['adv'])} points. "
        "The earlier run (Table~\\ref{tab:weights}) gave \\WtEqualPCMean{} points with an interval from "
        "\\WtEqualPCLo{} to \\WtEqualPCHi{}, so in both "
        "runs equal weights cut the advantage by more than half, but whether its interval reaches zero differs between "
        "runs. Raising the driver-duration weight to 0.25, with the other weights scaled down, lowered service "
        f"about as much as equal weights did ({iv(du['diff'])} against {iv(e['diff'])} points from the original "
        f"vector), and raising the fleet weight cost {iv(fu['diff'])} points. The run cannot separate the two "
        f"effects: the duration-raised vector minus the fleet-raised one was {iv(dvf)} points. The stored "
        "candidates suggest why the duration weight matters. Compared at the same instance and buffer, the "
        "duration-heavy candidates used only "
        f"{f2(-pf['duration_up'])} fewer vehicles, against {f2(-pf['fleet_up'])} for the fleet-heavy ones, yet their "
        f"success on the screening bank fell more ({f1(-ps['duration_up'])} against {f1(-ps['fleet_up'])} points): "
        f"they shortened driver duration by {-pdur:.0f} minutes per plan on average and raised the slack deficit, so "
        "less waiting time was left to absorb delays. A heavier duration weight thus appears to remove slack that "
        "screening relies on. Of the 53 runs with the original vector, 39 ran on the first day while other analyses "
        "were also running on the machine, and the other runs of the bracketing ran later with the machine "
        "otherwise idle; because OR-Tools stops at a wall-clock limit, this may affect the comparison slightly.")


# --------------------------------------------------------------------------- Gehring-Homberger
def gh_section():
    s = load_json("results/gh200_summary.json")
    if not s:
        return False
    rows = s["rows"]
    failed = [k for k, v in rows.items() if v["anchors"] != "ok"]
    for k in failed:
        assert rows[k]["hgs_conservative"] is None and rows[k]["hgs_capped_cons"] is None, k
    ok = [v for k, v in rows.items() if v["anchors"] == "ok"]
    d = s["capped_cons_minus_conservative"]
    widths = {}
    import gh_benchmark as gb
    for k in failed:
        _, sec = gb.parse(k)
        widths[k] = min(b - a for _, a, b in sec["TIME_WINDOW_SECTION"][1:])
    tab_rows = []
    for cls in ("R1", "RC1"):
        vs = [v for k, v in rows.items() if k.startswith(cls + "_")]
        sv = lambda c: float(np.mean([x[c] or 0.0 for x in vs]))
        tab_rows.append(f"{cls} & {len(vs)} & {sum(x['anchors'] == 'ok' for x in vs)} & "
                        f"{sum(bool(x['admitted']) for x in vs)} & {f1(sv('hgs_nominal'))} & "
                        f"{f1(sv('hgs_conservative'))} & {f1(sv('hgs_capped_cons'))}")
    MACROS.update({"GhAdmitted": str(s["admitted"]), "GhAttempted": str(len(ok)), "GhDiff": f1(d[0]),
                   "GhDiffLo": f1(d[1]), "GhDiffHi": f1(d[2]), "GhCapped": f1(s["pooled"]["hgs_capped_cons"]),
                   "GhCons": f1(s["pooled"]["hgs_conservative"])})
    names = " and ".join(k.replace("_", "\\_") for k in failed)
    text = [
        r"\subsection{Gehring--Homberger instances}\label{sec:gh}", "",
        "As a harder external check, the HGS pipeline of the second study was run on the 20 Gehring--Homberger "
        "instances of classes R1 and RC1 with 200 customers \\cite{gehring1999} "
        "(\\texttt{code/gh\\_benchmark.py}; exploratory). The mapping follows the Solomon check, except that "
        "the depot horizon of 634 time units is scaled to the 600-minute shift and the coordinates are scaled so "
        "that the benchmark's unit-speed travel corresponds to 40~km/h; capacity and fleet are kept. "
        f"On {names}, where all or most windows are only {min(widths.values())} time units wide, neither the "
        "OR-Tools anchor solves nor HGS at conservative speed found a plan, so the procedure could not run there. "
        f"Screening admitted a plan on {s['admitted']} of the other {len(ok)} instances "
        f"(Table~\\ref{{tab:gh}}). Where conservative speed had a plan, the HGS capped procedure exceeded it by "
        f"{iv(d)} points ({sum(v['hgs_conservative'] is not None for v in ok)} instances), and over "
        f"all 20 instances it pooled {f1(s['pooled']['hgs_capped_cons'])}\\% against "
        f"{f1(s['pooled']['hgs_conservative'])}\\% for conservative speed and {f1(s['pooled']['hgs_nominal'])}\\% "
        "for the nominal plan.", "",
        tab("Gehring--Homberger instances with 200 customers (exploratory, HGS pipeline): instances, instances where "
            "the anchor solves found a plan, instances admitted by screening, and pooled validated service-event "
            "probability (\\%) of the HGS nominal plan, HGS conservative speed and the HGS capped procedure with "
            "conservative fallback. A missing plan scores zero.",
            "tab:gh", r"@{}lrrrrrr@{}", r"Class & Inst. & Anchors & Admitted & Nominal & Conservative & Capped",
            tab_rows),
    ]
    (ROOT / "paper/gh_results.tex").write_text("\n".join(text))
    return True


def main():
    fallback_section()
    robust_extra()
    weight_bracketing()
    gh_section()
    (ROOT / "paper/result_macros_v12.tex").write_text(
        "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k, v in MACROS.items()) + "\n")
    print(json.dumps(MACROS, indent=1))


if __name__ == "__main__":
    main()
