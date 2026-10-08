"""Generate the manuscript text, tables and macros for confirmatory study 2
(HGS generator and fallback rule) and its exploratory development run.

Reads results/confirm2 (both halves and analysis_output.txt), results/hgs_dev
and the development OR-Tools records in results/v7. Writes
paper/result_macros_v9.tex, paper/study2_results.tex and
paper/study2_appendix.tex.

Study-2 quantities are computed with the frozen protocol-2 functions
(validation included) and must equal the saved output of the run; the script
stops if they do not.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import confirm_analysis_hgs as c2
from exact_display import check_against, exact_analysis
from analyse_v8 import f1, interval, table

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "results" / "confirm2"


def confirmatory():
    stage1 = [str(CONF / f"study_v6_n{n}.json") for n in (20, 50, 100, 200)]
    ort, hgs = c2.validate(stage1, CONF / "v7", CONF / "hgs", ROOT / "FROZEN_MANIFEST_2.json", ROOT)
    units = [c2.unit(s, ort[s], hgs[s]) for s in sorted(hgs)]
    out = {"mode": "CONFIRMATORY (validated against the frozen protocol 2)", **c2.analyse(units, True)}
    saved = json.loads((CONF / "analysis_output.txt").read_text())
    assert json.loads(json.dumps(out)) == saved, "study-2 output differs from the saved confirmatory run"
    out = {"mode": out["mode"], **exact_analysis(c2, units, True)}   # display values, see exact_display.py
    check_against(out, saved)
    fb = [u for u in units if not u["ort_capped_selected"]]
    changed = [u for u in fb if ort[u["seed"]]["configurations"]["conservative"] is not None]
    return out, units, fb, changed


def development():
    load = lambda d: {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
                      for f in sorted(glob.glob(str(d / "instance_*.json")))}
    ort, hgs = load(ROOT / "results" / "v7"), load(ROOT / "results" / "hgs_dev")
    assert len(hgs) == 53 and set(hgs) <= set(ort)
    units = [c2.unit(s, ort[s], hgs[s]) for s in sorted(hgs)]
    return exact_analysis(c2, units, False)


def main():
    out, units, fb, changed = confirmatory()
    dev = development()
    g = {h: out[h] for h in ("G1", "G2", "G3", "G4")}
    pooled = out["pooled_mean_pp"]
    desc = out["descriptive_by_size"]
    large = [u for u in units if u["customers"] >= 100]
    verdict = lambda v: {"CONFIRMED": "confirmed", "NOT CONFIRMED": "not confirmed"}.get(v, "estimate only")
    changes = [100 * (u["ort_capped_cons"] - u["ort_capped"]) for u in changed]

    macros = {
        "CtwoGOneMean": f1(g["G1"]["mean_pp"]), "CtwoGOneLo": f1(g["G1"]["lo_pp"]), "CtwoGOneHi": f1(g["G1"]["hi_pp"]),
        "CtwoGTwoMean": f1(g["G2"]["mean_pp"]), "CtwoGTwoLo": f1(g["G2"]["lo_pp"]), "CtwoGTwoHi": f1(g["G2"]["hi_pp"]),
        "CtwoGThreeMean": f1(g["G3"]["mean_pp"]), "CtwoGThreeLo": f1(g["G3"]["lo_pp"]), "CtwoGThreeHi": f1(g["G3"]["hi_pp"]),
        "CtwoGFourMean": f1(g["G4"]["mean_pp"]), "CtwoGFourLo": f1(g["G4"]["lo_pp"]), "CtwoGFourHi": f1(g["G4"]["hi_pp"]),
        "CtwoCommon": str(g["G1"]["k"]),
        "CtwoPooledHGSCons": f1(pooled["hgs_conservative"]), "CtwoPooledHGSK": f1(pooled["hgs_capped_cons"]),
        "CtwoPooledORTK": f1(pooled["ort_capped"]), "CtwoPooledORTKc": f1(pooled["ort_capped_cons"]),
        "CtwoORTKAdmitted": str(53 - len(fb)), "CtwoORTKFallbacks": str(len(fb)),
        "CtwoFallbacksChanged": str(len(changed)),
        "CtwoHGSKAdmittedLarge": str(sum(u["hgs_capped_selected"] for u in large)),
        "CtwoHGSPAdmittedLarge": str(sum(u["hgs_uncapped_selected"] for u in large)),
        "CtwoLarge": str(len(large)),
        "DevHGSGOneMean": f1(dev["G1"]["mean_pp"]), "DevHGSGOneLo": f1(dev["G1"]["lo_pp"]),
        "DevHGSGOneHi": f1(dev["G1"]["hi_pp"]), "DevHGSPooledK": f1(dev["pooled_mean_pp"]["hgs_capped_cons"]),
    }
    (ROOT / "paper/result_macros_v9.tex").write_text(
        "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k, v in macros.items()) + "\n")

    rows = [
        f"G1 (primary) & HGS capped with conservative fallback minus HGS conservative, {g['G1']['k']} instances & "
        f"{interval((g['G1']['mean_pp'], g['G1']['lo_pp'], g['G1']['hi_pp']))} & 97.5\\% & {verdict(g['G1']['verdict'])}",
        f"G2 (primary) & OR-Tools capped, conservative minus slack-aware fallback, {g['G2']['k']} instances & "
        f"{interval((g['G2']['mean_pp'], g['G2']['lo_pp'], g['G2']['hi_pp']))} & 97.5\\% & {verdict(g['G2']['verdict'])}",
        f"G3 & OR-Tools uncapped, conservative minus slack-aware fallback, {g['G3']['k']} instances & "
        f"{interval((g['G3']['mean_pp'], g['G3']['lo_pp'], g['G3']['hi_pp']))} & 95\\% & {verdict(g['G3']['verdict'])}",
        f"G4 & HGS minus OR-Tools, both capped with conservative fallback, {g['G4']['k']} instances & "
        f"{interval((g['G4']['mean_pp'], g['G4']['lo_pp'], g['G4']['hi_pp']))} & 95\\% & estimate only",
    ]
    text = [
        r"\subsection{Second confirmatory study}\label{sec:confirmatory2}", "",
        "In the exploratory run on the 53 development instances"
        f", the HGS capped procedure with conservative fallback exceeded HGS conservative-speed planning by "
        f"{f1(dev['G1']['mean_pp'])} points, with pooled service of {f1(dev['pooled_mean_pp']['hgs_capped_cons'])}\\%. "
        r"Table~\ref{tab:confirmatory2} gives the prespecified results on the 53 new instances of the second study.",
        "",
        table("Second confirmatory study on 53 new instances. Differences are in percentage points of validated "
              "service-event probability; intervals are paired bootstrap intervals over instances. G1 uses the "
              f"{g['G1']['k']} instances where HGS conservative-speed planning returned a plan.",
              "tab:confirmatory2", r"@{}>{\raggedright\arraybackslash}p{1.9cm}>{\raggedright\arraybackslash}p{4.4cm}"
              r">{\raggedright\arraybackslash}p{3.3cm}cc@{}",
              r"Hypothesis & Quantity & Estimate [interval] & Level & Decision", rows, size="footnotesize"),
        f"G1 was confirmed. With the HGS generator, screening with capped contraction exceeded conservative padding by "
        f"{f1(g['G1']['mean_pp'])} points, and pooled service probability reached {f1(pooled['hgs_capped_cons'])}\\% "
        f"against {f1(pooled['hgs_conservative'])}\\% for HGS conservative speed. Capping was essential with this "
        f"generator: at 100 and 200 customers the HGS capped family was admitted on "
        f"{sum(u['hgs_capped_selected'] for u in large)} of {len(large)} instances, and the uncapped family on "
        f"{sum(u['hgs_uncapped_selected'] for u in large)}.", "",
        f"G2 was not confirmed. The OR-Tools capped procedure admitted a plan on {53 - len(fb)} of 53 instances and fell "
        f"back on {len(fb)}. On {len(fb) - len(changed)} of those no conservative-speed plan existed, "
        f"so both rules returned the same plan. On the remaining {len(changed)} the conservative fallback changed "
        f"service probability by " + (lambda xs: ", ".join(xs[:-1]) + " and " + xs[-1])(
            [f"{c:+.1f}".replace("-", "$-$") for c in changes]) + " points. The post hoc gain seen for the capped procedure "
        f"in the first study did not replicate. For the uncapped procedure, which falls back more often, the conservative "
        f"fallback helped (G3, {f1(g['G3']['mean_pp'])} points).", "",
        f"Under the capped procedure with conservative fallback, the two generators differed by "
        f"{f1(g['G4']['mean_pp'])} points (G4), with a 95\\% interval from {f1(g['G4']['lo_pp'])} to {f1(g['G4']['hi_pp'])}. "
        "No equivalence margin was prespecified, so this interval bounds the difference but does not establish "
        "equivalence. The HGS $\\beta=0$ plan, which lacks the slack term, was a weak fallback: the uncapped HGS procedure "
        f"pooled {f1(pooled['hgs_procedure_slack'])}\\% with it and {f1(pooled['hgs_procedure_cons'])}\\% with the "
        "conservative fallback (descriptive).", "",
    ]
    (ROOT / "paper/study2_results.tex").write_text("\n".join(text))

    srows = []
    for n in ("20", "50", "100", "200"):
        d = desc[n]
        srows.append(f"{n} & {d['instances']} & {d['ort_capped_admitted']} & {f1(d['ort_capped'])} & "
                     f"{f1(d['ort_capped_cons'])} & {d['hgs_capped_admitted']} & {f1(d['hgs_conservative'])} & "
                     f"{f1(d['hgs_capped_cons'])}")
    (ROOT / "paper/study2_appendix.tex").write_text(table(
        "Second confirmatory study by size (descriptive): instances admitted by the capped procedure, and mean "
        "validated service-event probability (\\%) over all instances, including fallbacks.",
        "tab:study2-size", r"@{}rrrrrrrr@{}",
        r"$n$ & Inst. & \multicolumn{3}{c}{OR-Tools capped} & \multicolumn{3}{c}{HGS} \\"
        r" & & Admitted & Slack fb. & Cons. fb. & Admitted & Conservative & Capped, cons. fb.",
        srows, size="footnotesize"))
    print(json.dumps(macros, indent=1))


if __name__ == "__main__":
    main()
