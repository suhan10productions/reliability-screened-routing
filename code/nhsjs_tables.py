"""Tables, macros and figure for the NHSJS version of the manuscript (paper_nhsjs/).

Nothing here computes a new result except the summary of the exploratory padding
sweep (code/padding_sweep.py), which this script reads from its records. The
development tables are copied from the files analyse_v7.py writes, the primary
hypotheses take their estimates from the generated result macros and their
decisions from the saved output of the frozen analysis programs.

Run after analyse_v7 ... analyse_v12 and padding_sweep.py --summarise:
  cd code && PYTHONPATH=. python3 nhsjs_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from itor_tables import PAPER, ROOT, compact_screen, extract_table, f1, f2, verdict

OUT = ROOT / "paper_nhsjs"


def primaries_table():
    p1 = json.loads((ROOT / "results/confirm/analysis_output.txt").read_text())
    p2 = json.loads((ROOT / "results/confirm2/analysis_output.txt").read_text())
    pa = json.loads((ROOT / "results/confirm_robust_analysis_output.json").read_text())
    pb = json.loads((ROOT / "results/confirm3_fallback_analysis_output.json").read_text())
    for d in (p1, p2, pa, pb):
        assert d["mode"].lower().startswith("confirmatory"), d["mode"]
    V = {"H1": verdict(p1["H1_P_minus_C"]["verdict"]), "H2": verdict(p1["H2_K_minus_P"]["verdict"]),
         "G1": verdict(p2["G1"]["verdict"]), "G2": verdict(p2["G2"]["verdict"]),
         "R1": verdict(pa["R1"]["verdict"]), "R2": verdict(pa["R2"]["verdict"]),
         "F1": verdict(pb["F1"]["verdict"]), "F2": verdict(pb["F2"]["verdict"])}
    assert sum(v == "confirmed" for v in V.values()) == 7 and V["G2"] == "not confirmed"
    rows = [
        ("1", "H1", r"Original procedure minus 20\% padding (\ConfCommon{} instances)", r"\ConfHOneMean{} [\ConfHOneLo, \ConfHOneHi]"),
        ("1", "H2", r"Capped minus original procedure (\ConfInstances{} instances)", r"\ConfHTwoMean{} [\ConfHTwoLo, \ConfHTwoHi]"),
        ("2", "G1", r"Capped procedure with HGS minus 20\% padding with HGS (\CtwoCommon{} instances)", r"\CtwoGOneMean{} [\CtwoGOneLo, \CtwoGOneHi]"),
        ("2", "G2", r"Conservative minus slack-aware fallback, capped OR-Tools procedure", r"\CtwoGTwoMean{} [\CtwoGTwoLo, \CtwoGTwoHi]"),
        ("3A", "R1", r"Screened robust model minus capped OR-Tools procedure (\PaInstances{} instances)", r"\PaROne{} [\PaROneLo, \PaROneHi]"),
        ("3A", "R2", r"Screened robust model minus capped HGS procedure (45 instances)", r"\PaRTwo{} [\PaRTwoLo, \PaRTwoHi]"),
        ("3B", "F1", r"Best-screened minus default fallback, capped OR-Tools procedure", r"\PbFOne{} [\PbFOneLo, \PbFOneHi]"),
        ("3B", "F2", r"Best-screened minus default fallback, capped HGS procedure", r"\PbFTwo{} [\PbFTwoLo, \PbFTwoHi]"),
    ]
    body = [f"{st} & {h} & {what} & {est} & {V[h]}\\\\" for st, h, what, est in rows]
    return "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small",
        r"\caption{The eight primary hypotheses of the three confirmatory studies. Each was fixed and publicly "
        r"timestamped before its instances were solved. Estimates are differences in validated service probability "
        r"(percentage points) with 97.5\% paired bootstrap intervals over instances; a hypothesis is confirmed when "
        r"its interval lies above zero.}",
        r"\label{tab:primaries}",
        r"\begin{tabular}{@{}cl>{\raggedright\arraybackslash}p{7.2cm}>{\raggedright\arraybackslash}p{2.9cm}l@{}}",
        r"\toprule", r"Study & & Contrast & Estimate [interval] & Decision\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])


def padding_outputs():
    s = json.loads((ROOT / "results/padding_sweep_summary.json").read_text())
    lv = s["levels"]
    levels = sorted(int(k) for k in lv)
    cap = s["capped"]
    N = s["instances"]
    rows = []
    for k in levels:
        v = lv[str(k)]
        d = v["service_minus_capped_on_plans"]
        dist, fleet = v["distance_vs_capped_pct"], v["fleet_minus_capped"]
        rows.append(f"{k}\\% & {v['with_plan']}/{N} & {f1(v['pooled_service'])} & {f1(v['service_on_plans'])} & "
                    f"{f1(v['capped_on_plans'])} & {f1(d[0])} [{f1(d[1])}, {f1(d[2])}] & {f1(dist[0])} & {f2(fleet[0])}\\\\")
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Padding every trip by a fixed percentage on the " + str(N) + r" development instances "
        r"(exploratory). \emph{Plans}: instances on which the padded planner found a plan. \emph{All}: pooled "
        r"service over all instances, an instance without a plan scoring zero. The next three columns use only the "
        r"instances with a padded plan: the padded plans' service, the capped screening procedure's service on the "
        r"same instances, and the difference (padding minus screening, percentage points, 95\% paired bootstrap "
        r"interval). Distance (\%) and vehicles are also padding minus screening on those instances. Over all "
        r"instances the capped procedure pooled " + f1(cap["pooled_service"]) + r"\%.}",
        r"\label{tab:padding}",
        r"\begin{tabular}{@{}rrrrrlrr@{}}", r"\toprule",
        r" & & \multicolumn{1}{c}{All} & \multicolumn{3}{c}{Instances with a padded plan} & & \\",
        r"\cmidrule(lr){3-3}\cmidrule(lr){4-6}",
        r"Padding & Plans & Pooled & Padded & Screened & Difference & Distance & Vehicles\\", r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    tags = {0: "Zero", 10: "Ten", 20: "Twenty", 30: "Thirty", 40: "Forty", 50: "Fifty"}
    best = max(levels, key=lambda k: lv[str(k)]["pooled_service"])
    macros = {"PadInstances": str(N), "PadCapPooled": f1(cap["pooled_service"]),
              "PadBestLevel": str(best), "PadBestPooled": f1(lv[str(best)]["pooled_service"]),
              "PadBestDiff": f1(lv[str(best)]["service_minus_capped"][0]),
              "PadBestDiffLo": f1(lv[str(best)]["service_minus_capped"][1]),
              "PadBestDiffHi": f1(lv[str(best)]["service_minus_capped"][2])}
    for k in levels:
        v, t = lv[str(k)], tags[k]
        d = v["service_minus_capped_on_plans"]
        macros.update({f"Pad{t}Pooled": f1(v["pooled_service"]), f"Pad{t}Plans": str(v["with_plan"]),
                       f"Pad{t}NoPlan": str(N - v["with_plan"]),
                       f"Pad{t}OnPlans": f1(v["service_on_plans"]), f"Pad{t}CapOnPlans": f1(v["capped_on_plans"]),
                       f"Pad{t}Diff": f1(d[0]), f"Pad{t}DiffLo": f1(d[1]), f"Pad{t}DiffHi": f1(d[2]),
                       f"Pad{t}Dist": f1(v["distance_vs_capped_pct"][0]),
                       f"Pad{t}DistAbs": f1(abs(v["distance_vs_capped_pct"][0])), f"Pad{t}Fleet": f2(v["fleet_minus_capped"][0])})
    # figure: service against padding level
    blue, orange, ink, muted = "#2a78d6", "#eb6834", "#1a1a19", "#6b6a64"
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ys = [lv[str(k)]["pooled_service"] for k in levels]
    ci = [lv[str(k)]["pooled_service_ci"] for k in levels]
    ax.vlines(levels, [c[1] for c in ci], [c[2] for c in ci], color=blue, alpha=0.5, linewidth=2)
    ax.plot(levels, ys, marker="o", markersize=8, linewidth=2, color=blue,
            markeredgecolor="white", markeredgewidth=1.5, label="Padding, all instances (no plan scores 0)")
    yp = [lv[str(k)]["service_on_plans"] for k in levels]
    ax.plot(levels, yp, marker="s", markersize=7, linewidth=1.5, linestyle=(0, (4, 2)), color=blue, alpha=0.75,
            markeredgecolor="white", label="Padding, only instances where it found a plan")
    cc = cap["pooled_service_ci"]
    ax.axhspan(cc[1], cc[2], color=orange, alpha=0.12, linewidth=0)
    ax.axhline(cap["pooled_service"], color=orange, linestyle="--", linewidth=2,
               label="Capped screening procedure, all instances")
    ax.axhline(95, color=muted, linestyle=":", linewidth=1)
    ax.text(levels[0], 96, "95% target", color=muted, fontsize=8, va="bottom")
    ax.set_xlabel("Padding of every planned trip (%), and instances with a padded plan", color=ink)
    ax.set_ylabel("Validated service probability (%)", color=ink)
    ax.set_xticks(levels)
    ax.set_xticklabels([f"{k}%\n{lv[str(k)]['with_plan']}/{N}" for k in levels])
    ax.set_ylim(0, 105)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=muted)
    fig.tight_layout()
    fig.savefig(OUT / "FigPadding.pdf")
    fig.savefig(OUT / "FigPadding.png", dpi=300)
    plt.close(fig)
    return table, macros


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "tab_paired.tex").write_text(extract_table(PAPER / "results_summary_v7.tex", "tab:paired")
                                        .replace(" on the same subsets as Table~\\ref{tab:matched}",
                                                 " on the 46 development instances where 20\\% padding found a plan"))
    (OUT / "tab_screen.tex").write_text(compact_screen(extract_table(PAPER / "results_summary_v7.tex", "tab:screen")))
    (OUT / "tab_primaries.tex").write_text(primaries_table())
    table, macros = padding_outputs()
    (OUT / "tab_padding.tex").write_text(table)
    (OUT / "result_macros_nhsjs.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()))
    print("nhsjs tables ok")


if __name__ == "__main__":
    main()
