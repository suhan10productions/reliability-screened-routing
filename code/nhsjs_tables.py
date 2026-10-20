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

import numpy as np
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


CITY_WORDS = {3: "three", 4: "four", 5: "five"}


def amazon_outputs():
    runs = {"": "amazon_summary.json", "D": "amazon_summary_nyc_days.json", "T": "amazon_summary_nyc_total.json"}
    S = {k: json.loads((ROOT / "results" / f).read_text()) for k, f in runs.items()}
    s, rows = S[""], S[""]["rows"]
    N = s["instances"]
    for k, v in S.items():
        assert v["instances"] == N == 40, (k, v["instances"])
        assert v["plans"] == s["plans"], k                 # planning does not depend on the delay model
    plans = {"nominal": s["plans"]["nominal"], "conservative": s["plans"]["conservative"],
             "capped": sum(1 for r in rows if r["has_nominal"]), "screened_conservative": sum(1 for r in rows if r["has_nominal"])}
    names = [("nominal", "Nominal plan (no protection)"), ("conservative", "20\\% padding"),
             ("capped", "Capped screening procedure"), ("screened_conservative", "Screened conservative")]
    cell = lambda v, k: f"{f1(v['pooled'][k][0])} [{f1(v['pooled'][k][1])}, {f1(v['pooled'][k][2])}]"  # noqa: E731
    body = [f"{label} & {plans[k]}/{N} & {cell(S[''], k)} & {cell(S['D'], k)} & {cell(S['T'], k)}\\\\"
            for k, label in names]
    adm = lambda key: " & ".join(str(S[x][key]) for x in ("", "D", "T"))  # noqa: E731
    body += [r"\midrule", r"Admitted, capped procedure & & " + adm("admitted") + r"\\",
             r"Admitted, screened conservative & & " + adm("screened_conservative_admitted") + r"\\"]
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Real delivery routes: " + str(N) + r" Amazon routes from " + CITY_WORDS[s["cities"]] +
        r" US cities (exploratory), under the assumed delay model and under the two delay models fitted to New York "
        r"taxi trips (Table~\ref{tab:nyc}). \emph{Plans}: routes on which the configuration produced a plan (the "
        r"same under every delay model). Pooled validated service probability (\%) with a 95\% bootstrap interval "
        r"over routes; a route without a plan scores zero. \emph{Admitted}: routes on which a candidate passed the "
        r"screen.}",
        r"\label{tab:amazon}",
        r"\begin{tabular}{@{}lclll@{}}", r"\toprule",
        r" & & \multicolumn{3}{c}{Pooled service under the delay model} \\",
        r"Configuration & Plans & Assumed & NYC, day to day & NYC, all variation\\", r"\midrule", *body,
        r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    stops = sorted(r["stops"] for r in rows)
    cust = sorted(r["customers"] for r in rows)
    m = {"AmzRoutes": str(N), "AmzStations": str(len({r["station"] for r in rows})),
         "AmzStopsMin": str(stops[0]), "AmzStopsMax": str(stops[-1]), "AmzStopsMed": str(int(np.median(stops))),
         "AmzCustMin": str(cust[0]), "AmzCustMax": str(cust[-1]),
         "AmzNomPlans": str(plans["nominal"]), "AmzConsPlans": str(plans["conservative"]),
         "AmzNoPlan": str(N - plans["nominal"]), "AmzConsNoPlan": str(N - plans["conservative"]),
         "AmzNoPlanCustMin": str(s["no_plan_customers"][0]), "AmzNoPlanCustMax": str(s["no_plan_customers"][1]),
         "AmzCities": CITY_WORDS[s["cities"]],
         "AmzWindowShare": f"{100 * s['amazon_windows']['stops_with_window'] / s['amazon_windows']['stops']:.0f}",
         "AmzWindowLo": f"{s['amazon_windows']['width_hours_quartiles'][0]:.0f}",
         "AmzWindowHi": f"{s['amazon_windows']['width_hours_quartiles'][2]:.0f}"}
    for t, v in S.items():
        P = v["pooled"]
        d1, d2, dw = v["capped_minus_conservative"], v["screened_conservative_minus_conservative"], v["capped_minus_conservative_where_planned"]
        m.update({f"Amz{t}Nom": f1(P["nominal"][0]), f"Amz{t}Cons": f1(P["conservative"][0]),
                  f"Amz{t}Cap": f1(P["capped"][0]), f"Amz{t}Sc": f1(P["screened_conservative"][0]),
                  f"Amz{t}CapDiff": f1(d1[0]), f"Amz{t}CapDiffLo": f1(d1[1]), f"Amz{t}CapDiffHi": f1(d1[2]),
                  f"Amz{t}ScDiff": f1(d2[0]), f"Amz{t}ScDiffLo": f1(d2[1]), f"Amz{t}ScDiffHi": f1(d2[2]),
                  f"Amz{t}Both": str(v["where_planned"]), f"Amz{t}BothDiff": f1(dw[0]),
                  f"Amz{t}BothDiffLo": f1(dw[1]), f"Amz{t}BothDiffHi": f1(dw[2]),
                  f"Amz{t}FleetDiff": f2(v["fleet_capped_minus_conservative"][0]),
                  f"Amz{t}CapAdmitted": str(v["admitted"]), f"Amz{t}ScAdmitted": str(v["screened_conservative_admitted"]),
                  f"Amz{t}CapAdmittedNinetyFive": str(v["capped_admitted_at_least_95"]),
                  f"Amz{t}CapOnAdmitted": f1(v["capped_on_admitted"]),
                  f"Amz{t}FallbackRoutes": str(v["fallback_instances"]),
                  f"Amz{t}CapOnFallback": "--" if v["capped_on_fallback"] is None else f1(v["capped_on_fallback"]),
                  f"Amz{t}ConsOnFallback": "--" if v["conservative_on_fallback"] is None else f1(v["conservative_on_fallback"])})
    diffs = [S[t]["capped_minus_conservative"][0] for t in S]
    m.update({"AmzCapDiffMin": f1(min(diffs)), "AmzCapDiffMax": f1(max(diffs))})
    # the New York calibration
    c = json.loads((ROOT / "results/nyc_calibration.json").read_text())
    prof = c["profile"]
    label = lambda p: f"{p['from_hour']:02d}:00--{p['to_hour']:02d}:00"  # noqa: E731
    nrows = [f"{label(p)} & {p['assumed']:.1f} & {p['multiplier']:.2f} & {p['zone_pairs']:,}\\\\".replace(",", "{,}")
             for p in prof]
    ntable = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small",
        r"\caption{The delay model fitted to " + f"{c['trips_used'] / 1e6:.1f}" + r" million weekday New York "
        r"yellow-taxi trips (January--March 2024). Time-of-day multipliers of travel time relative to "
        r"09:00--17:00, from zone pairs with at least 20 trips in both periods; the spread $\sigma$ and the "
        r"day-common share $\rho$ of the random factor are estimated in two ways (see text).}",
        r"\label{tab:nyc}",
        r"\begin{tabular}{@{}lccr@{}}", r"\toprule",
        r"Period & Assumed & Fitted & Zone pairs\\", r"\midrule", *nrows, r"\midrule",
        f"$\\sigma$ & 0.20 & {c['sigma_between_days']:.2f} (day to day), {c['sigma_total']:.2f} (all) & \\\\",
        f"$\\rho$ & 0.50 & {c['rho_between_days']:.2f} (day to day), {c['rho_total']:.2f} (all) & \\\\",
        r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    m.update({"NycTripsM": f"{c['trips_used'] / 1e6:.1f}", "NycRawM": f"{c['trips_raw'] / 1e6:.1f}",
              "NycWeekdays": str(c["weekdays"]),
              "NycEarly": f"{prof[0]['multiplier']:.2f}", "NycAm": f"{prof[1]['multiplier']:.2f}",
              "NycPm": f"{prof[3]['multiplier']:.2f}", "NycLate": f"{prof[4]['multiplier']:.2f}",
              "NycAmFaster": f"{100 * (1 - prof[1]['multiplier']):.0f}",
              "NycPmFaster": f"{100 * (1 - prof[3]['multiplier']):.0f}",
              "NycSigmaDays": f"{c['sigma_between_days']:.2f}", "NycSigmaTotal": f"{c['sigma_total']:.2f}",
              "NycRhoDays": f"{c['rho_between_days']:.2f}", "NycRhoTotal": f"{c['rho_total']:.2f}"})
    return table, ntable, m

def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "tab_paired.tex").write_text(extract_table(PAPER / "results_summary_v7.tex", "tab:paired")
                                        .replace(" on the same subsets as Table~\\ref{tab:matched}",
                                                 " on the 46 development instances where 20\\% padding found a plan"))
    (OUT / "tab_screen.tex").write_text(compact_screen(extract_table(PAPER / "results_summary_v7.tex", "tab:screen")))
    (OUT / "tab_primaries.tex").write_text(primaries_table())
    (OUT / "tab_gh.tex").write_text(extract_table(PAPER / "gh_results.tex", "tab:gh"))
    table, macros = padding_outputs()
    (OUT / "tab_padding.tex").write_text(table)
    atable, ntable, amacros = amazon_outputs()
    (OUT / "tab_amazon.tex").write_text(atable)
    (OUT / "tab_nyc.tex").write_text(ntable)
    macros.update(amacros)
    (OUT / "result_macros_nhsjs.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()))
    print("nhsjs tables ok")


if __name__ == "__main__":
    main()
