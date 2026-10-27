"""Tables, macros and figures for the IJSS: Operations & Logistics manuscript (paper_ijss/).

Reads only stored records: results/certify_summary.json (code/certify.py),
results/frontier_summary.json (code/frontier.py), results/wrong_model_summary.json
(code/wrong_model.py) and results/amazon_search_check.json
(code/amazon_search_check.py). The tables shared with the NHSJS version are
copied from paper_nhsjs/ (run code/nhsjs_tables.py first).

Run:
  cd code && PYTHONPATH=. python3 ijss_tables.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from itor_tables import f1, f2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper_ijss"
SHARED = ("tab_paired.tex", "tab_padding.tex", "tab_screen.tex", "tab_primaries.tex", "tab_gh.tex",
          "tab_amazon.tex", "tab_nyc.tex", "result_macros_nhsjs.tex", "FigPadding.pdf", "FigPadding.png", "Fig1.png")
STUDY_COLS = (("development", "Dev."), ("confirmatory 1", "Conf.\\ 1"), ("confirmatory 2", "Conf.\\ 2"),
              ("amazon assumed", "Amazon"), ("amazon nyc_days", "NYC d."), ("amazon nyc_total", "NYC all"))


def certify_table(c):
    rows = [("nominal", "Nominal plan (OR-Tools)"), ("conservative", "20\\% padding (OR-Tools)"),
            ("procedure", "Original procedure"),
            ("capped_procedure", "Capped procedure"), ("screened_conservative", "Screened conservative"),
            ("hgs_nominal", "Nominal plan (HGS)"), ("hgs_conservative", "20\\% padding (HGS)"),
            ("hgs_capped_cons", "Capped procedure (HGS)")]
    body = []
    for key, label in rows:
        cells = []
        for s, _ in STUDY_COLS:
            v = c["studies"][s].get(key)
            cells.append("--" if v is None else f"{v['certified']}/{v['with_plan']}")
        body.append(label + " & " + " & ".join(cells) + "\\\\")
    m = {"CertTotal": str(c["all_certified"]), "CertFails": str(c["all_fails_certificate"]),
         "CertBelow": str(c["all_test_below_target"])}
    pad_syn = sum(c["studies"][s][k]["certified"] for s in ("development", "confirmatory 1", "confirmatory 2")
                  for k in ("conservative", "hgs_conservative") if k in c["studies"][s])
    pad_syn_n = sum(c["studies"][s][k]["with_plan"] for s in ("development", "confirmatory 1", "confirmatory 2")
                    for k in ("conservative", "hgs_conservative") if k in c["studies"][s])
    m.update({"CertPadSyn": str(pad_syn), "CertPadSynN": str(pad_syn_n)})
    for s, tag in (("development", "Dev"), ("confirmatory 1", "Cone"), ("confirmatory 2", "Ctwo"),
                   ("amazon assumed", "Amz"), ("amazon nyc_days", "AmzD"), ("amazon nyc_total", "AmzT")):
        for k, kt in (("capped_procedure", "Cap"), ("conservative", "Pad"), ("screened_conservative", "Sc"),
                      ("hgs_capped_cons", "HCap")):
            v = c["studies"][s].get(k)
            if v is not None:
                m[f"Cert{tag}{kt}"] = str(v["certified"])
                m[f"Cert{tag}{kt}N"] = str(v["with_plan"])
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Certified plans: plans whose exact one-sided 95\% lower bound on the success probability, "
        r"from the 5000 validation days, is at least 0.95, out of the plans the configuration produced. "
        r"Dev., Conf.~1 and Conf.~2: development and first two confirmatory studies (53 instances each); Amazon: "
        r"40 routes under the assumed delay model and under the two models fitted to New York traffic. On a "
        r"further 5000 fresh days, none of the " + m["CertTotal"] + r" certified plans in the table failed its "
        r"certificate (exact one-sided 95\% upper bound below 0.95).}",
        r"\label{tab:certify}",
        r"\begin{tabular}{@{}l" + "c" * len(STUDY_COLS) + r"@{}}", r"\toprule",
        "Configuration & " + " & ".join(h for _, h in STUDY_COLS) + r"\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    tab_total = sum(c["studies"][s][k]["certified"] for s, _ in STUDY_COLS for k, _ in rows if k in c["studies"][s])
    assert tab_total == c["all_certified"], (tab_total, c["all_certified"])
    return table, m


CAP_CERT_DEV = None    # set in main() from the certification summary


def frontier_outputs(fr):
    L = fr["levels"]
    N = fr["instances"]
    names = ["0.50", "0.70", "0.80", "0.90", "0.95", "0.95_certified", "0.99"]
    body = []
    for nm in names:
        v = L[nm]
        lab = ("95\\%, exact bound" if nm.endswith("certified") else f"{round(100 * v['q'])}\\%")
        dd = "--" if v["distance_pct_diff"] is None else f"{f1(v['distance_pct_diff'][0])} [{f1(v['distance_pct_diff'][1])}, {f1(v['distance_pct_diff'][2])}]"
        fd = "--" if v["fleet_diff"] is None else f"{f2(v['fleet_diff'][0])} [{f2(v['fleet_diff'][1])}, {f2(v['fleet_diff'][2])}]"
        body.append(f"{lab} & {v['reach_buffers']} & {v['reach_padding']} & {v['both']} & {dd} & {fd}\\\\")
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{The cost of reliability on the " + str(N) + r" development instances. For each level, the "
        r"number of instances on which the buffer family (13 capped candidates) and the padding family (0 to "
        r"50\%) contain a plan whose validated success probability reaches it, and, where both do, the paired "
        r"difference in cost between the cheapest such plans (buffers minus padding): distance in percent of the "
        r"plain distance plan, and vehicles. 95\% bootstrap intervals over instances. \emph{Exact bound}: the "
        r"Clopper--Pearson lower bound, rather than the estimate, must reach 95\%. Every row is descriptive: the "
        r"qualifying plan is found with the same validation days that judge it, so the counts show what each family "
        r"can reach, not what a procedure would select and certify (the capped procedure certified " + str(CAP_CERT_DEV) +
        r" of the " + str(N) + r" instances; Table~\ref{tab:certify}), and no row is a certificate in the sense of "
        r"Theorem~\ref{thm:cert}.}",
        r"\label{tab:frontier}",
        r"\begin{tabular}{@{}lccclll@{}}", r"\toprule",
        r" & \multicolumn{2}{c}{Instances reached} & & \multicolumn{2}{c}{Buffers minus padding} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){5-6}",
        r"Reliability & Buffers & Padding & Both & Distance (\%) & Vehicles\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    v95, vc, v99, v90 = L["0.95"], L["0.95_certified"], L["0.99"], L["0.90"]
    m = {"FrN": str(N), "FrBufNinetyFive": str(v95["reach_buffers"]), "FrPadNinetyFive": str(v95["reach_padding"]),
         "FrBothNinetyFive": str(v95["both"]),
         "FrDistNinetyFive": f1(v95["distance_pct_diff"][0]), "FrDistNinetyFiveLo": f1(v95["distance_pct_diff"][1]),
         "FrDistNinetyFiveHi": f1(v95["distance_pct_diff"][2]),
         "FrFleetNinetyFive": f2(v95["fleet_diff"][0]), "FrFleetNinetyFiveLo": f2(v95["fleet_diff"][1]),
         "FrFleetNinetyFiveHi": f2(v95["fleet_diff"][2]),
         "FrFleetNinetyFiveAbs": f2(abs(v95["fleet_diff"][0])),
         "FrFleetNinetyFiveAbsLo": f2(abs(v95["fleet_diff"][2])), "FrFleetNinetyFiveAbsHi": f2(abs(v95["fleet_diff"][1])),
         "FrBufCert": str(vc["reach_buffers"]), "FrPadCert": str(vc["reach_padding"]),
         "FrBufNinetyNine": str(v99["reach_buffers"]), "FrPadNinetyNine": str(v99["reach_padding"]),
         "FrBufNinety": str(v90["reach_buffers"]), "FrPadNinety": str(v90["reach_padding"]),
         "FrPadOnly": str(v95["reach_padding_only"])}
    assert v95["distance_pct_diff"][0] > 0 and v95["fleet_diff"][2] < 0     # the wording in the text assumes this
    # figure
    blue, orange, ink, muted = "#2a78d6", "#eb6834", "#1a1a19", "#6b6a64"
    qs = [L[k]["q"] for k in ("0.50", "0.60", "0.70", "0.80", "0.85", "0.90", "0.95", "0.99")]
    rb = [100 * L[k]["reach_buffers"] / N for k in ("0.50", "0.60", "0.70", "0.80", "0.85", "0.90", "0.95", "0.99")]
    rp = [100 * L[k]["reach_padding"] / N for k in ("0.50", "0.60", "0.70", "0.80", "0.85", "0.90", "0.95", "0.99")]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    x = [100 * q for q in qs]
    ax.plot(x, rb, marker="o", markersize=8, linewidth=2, color=blue, markeredgecolor="white", markeredgewidth=1.5,
            label="Buffer family (13 capped candidates)")
    ax.plot(x, rp, marker="s", markersize=7, linewidth=2, color=orange, markeredgecolor="white", markeredgewidth=1.5,
            label="Padding family (0 to 50%)")
    ax.set_xlabel("Required validated success probability (%)", color=ink)
    ax.set_ylabel("Instances where it can be reached (%)", color=ink)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=muted)
    fig.tight_layout()
    fig.savefig(OUT / "FigFrontier.pdf")
    fig.savefig(OUT / "FigFrontier.png", dpi=300)
    plt.close(fig)
    return table, m


def wrong_outputs(w):
    models = w["models"]
    rows = [("conservative", "20\\% padding"), ("capped_procedure", "Capped procedure"),
            ("screened_conservative", "Screened conservative")]
    body = []
    for key, label in rows:
        cells = []
        for mdl in ("nyc_days", "nyc_total"):
            s = models[mdl]["summary"]
            a, b = s[f"assumed:{key}"], s[f"fitted:{key}"]
            kept = "--" if a["certified_when_chosen"] == 0 else f"{a['certificate_kept']}/{a['certified_when_chosen']}"
            cells += [f"{f1(a['pooled'][0])}", kept,
                      f"{f1(b['pooled'][0])}"]
        body.append(label + " & " + " & ".join(cells) + "\\\\")
    syn = w["synthetic_misspecification"]["certificates"]
    srows = []
    labels = {"baseline": "Assumed model (new days)", "heavy_tails": "Heavy-tailed delays",
              "peak_noise": "More noise in the peaks", "incidents": "Random incidents",
              "strong_peak": "Stronger morning peak"}
    for mdl in ("baseline", "heavy_tails", "peak_noise", "incidents", "strong_peak"):
        c, h = syn[mdl]["capped_procedure"], syn[mdl]["hgs_capped_cons"]
        srows.append(f"{labels[mdl]} & {c['kept']}/{c['certified']} & {f1(c['mean_service'])} & "
                     f"{h['kept']}/{h['certified']} & {f1(h['mean_service'])}\\\\")
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{When the delay model is wrong. Top: the 40 Amazon routes, judged on 5000 fresh days under each "
        r"delay model fitted to New York traffic. \emph{Wrong}: plans chosen when the screen used the assumed model; "
        r"\emph{Right}: plans chosen when it used the fitted model. Pooled service (\%), and certificates (granted "
        r"under the model used for screening) that still hold. Bottom: plans certified under the assumed model on "
        r"the synthetic instances of the development and confirmatory studies, judged under delay models that "
        r"differ from it; certificates that still hold and the mean service (\%) of the certified plans.}",
        r"\label{tab:wrong}",
        r"\begin{tabular}{@{}lcccccc@{}}", r"\toprule",
        r" & \multicolumn{3}{c}{NYC, day-to-day variation} & \multicolumn{3}{c}{NYC, all variation}\\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r" & Wrong & Kept & Right & Wrong & Kept & Right\\", r"\midrule", *body,
        r"\midrule",
        r" & \multicolumn{2}{c}{Capped (OR-Tools)} & \multicolumn{2}{c}{Capped (HGS)} & & \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r"True delay model & Kept & Service & Kept & Service & & \\", r"\midrule", *[r + "" for r in
        [x.replace("\\\\", " & & \\\\") for x in srows]],
        r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    D, T = models["nyc_days"]["summary"], models["nyc_total"]["summary"]
    m = {}
    for tag, s in (("D", D), ("T", T)):
        d1, d2, d3 = s["assumed_capped_minus_assumed_padding"], s["assumed_screened_cons_minus_assumed_padding"], s["fitted_capped_minus_assumed_capped"]
        m.update({f"Wr{tag}CapPad": f1(d1[0]), f"Wr{tag}CapPadLo": f1(d1[1]), f"Wr{tag}CapPadHi": f1(d1[2]),
                  f"Wr{tag}ScPad": f1(d2[0]), f"Wr{tag}ScPadLo": f1(d2[1]), f"Wr{tag}ScPadHi": f1(d2[2]),
                  f"Wr{tag}Gain": f1(d3[0]), f"Wr{tag}GainLo": f1(d3[1]), f"Wr{tag}GainHi": f1(d3[2]),
                  f"Wr{tag}CapKept": str(s["assumed:capped_procedure"]["certificate_kept"]),
                  f"Wr{tag}CapCert": str(s["assumed:capped_procedure"]["certified_when_chosen"]),
                  f"Wr{tag}ScKept": str(s["assumed:screened_conservative"]["certificate_kept"]),
                  f"Wr{tag}ScCert": str(s["assumed:screened_conservative"]["certified_when_chosen"])})
    for mdl, tag in (("incidents", "Inc"), ("strong_peak", "Peak"), ("heavy_tails", "Tail"), ("peak_noise", "Noise")):
        c, h = syn[mdl]["capped_procedure"], syn[mdl]["hgs_capped_cons"]
        m.update({f"Wr{tag}Failed": str(c["certified"] - c["kept"]),
                  f"Wr{tag}Kept": str(c["kept"]), f"Wr{tag}Cert": str(c["certified"]), f"Wr{tag}Serv": f1(c["mean_service"]),
                  f"Wr{tag}HKept": str(h["kept"]), f"Wr{tag}HCert": str(h["certified"]), f"Wr{tag}HServ": f1(h["mean_service"])})
    return table, m


def stress_outputs(st):
    S = st["summary"]
    show = ("incidents", "strong_peak", "peak_noise", "heavy_tails", "baseline")
    head = {"incidents": "Incid.", "strong_peak": "Peak", "peak_noise": "Noise", "heavy_tails": "Tails", "baseline": "Assumed"}
    body = []
    for proc, label in (("capped_ortools", "Capped (OR-Tools)"), ("capped_hgs", "Capped (HGS)")):
        v = S[proc]
        body.append(r"\multicolumn{7}{@{}l}{\emph{" + label + "}}\\\\")
        for key, lab in (("single_cert_baseline", "Ordinary screen, certified under the assumed model"),
                         ("single_cert_all", "Ordinary screen, certified under all five models"),
                         ("stress_cert_all", "Stress screen, certified under all five models")):
            c = v[key]
            body.append(f"\\quad {lab} & {c['certified']}/{v['instances']} & " +
                        " & ".join(str(c["fails_by_model"][m]) for m in show) + "\\\\")
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Certifying against several delay models, on the synthetic instances of the development and "
        r"confirmatory studies. \emph{Certified}: plans certified, out of all instances. The other columns count "
        r"certified plans that failed their certificate on 5000 fresh days under each true delay model: random "
        r"incidents, a stronger morning peak, more noise in the peaks, heavy-tailed delays, and the assumed model. "
        r"The stress screen admits a candidate only if it passes under all five models.}",
        r"\label{tab:stress}",
        r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{6.6cm}cccccc@{}}", r"\toprule",
        r" & & \multicolumn{5}{c}{Failed certificates under the true model}\\", r"\cmidrule(lr){3-7}",
        "Configuration & Certified & " + " & ".join(head[m] for m in show) + r"\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    o, h = S["capped_ortools"], S["capped_hgs"]
    m = {"StOInst": str(o["instances"]), "StHInst": str(h["instances"]),
         "StOSingle": str(o["single_cert_baseline"]["certified"]), "StHSingle": str(h["single_cert_baseline"]["certified"]),
         "StOSingleIncFail": str(o["single_cert_baseline"]["fails_by_model"]["incidents"]),
         "StOSinglePeakFail": str(o["single_cert_baseline"]["fails_by_model"]["strong_peak"]),
         "StHSingleIncFail": str(h["single_cert_baseline"]["fails_by_model"]["incidents"]),
         "StHSinglePeakFail": str(h["single_cert_baseline"]["fails_by_model"]["strong_peak"]),
         "StOSingleAll": str(o["single_cert_all"]["certified"]), "StHSingleAll": str(h["single_cert_all"]["certified"]),
         "StOStress": str(o["stress_cert_all"]["certified"]), "StHStress": str(h["stress_cert_all"]["certified"]),
         "StStressFails": str(sum(sum(S[p]["stress_cert_all"]["fails_by_model"].values()) for p in S)),
         "StOFleet": f2(o["stress_minus_single_fleet"]), "StHFleet": f2(h["stress_minus_single_fleet"]),
         "StODist": f1(o["stress_minus_single_distance_pct"]), "StHDist": f1(h["stress_minus_single_distance_pct"]),
         "StOBoth": str(o["both_selected"]), "StHBoth": str(h["both_selected"]),
         "StOIncServ": f1(o["stress_cert_all"]["mean_test_success"]["incidents"]),
         "StOPeakServ": f1(o["stress_cert_all"]["mean_test_success"]["strong_peak"])}
    return table, m


def amazon_hgs_outputs(h):
    labels = {"assumed": "Assumed", "nyc_days": "NYC, day to day", "nyc_total": "NYC, all variation"}
    body, m = [], {}
    for mdl, tag in (("assumed", ""), ("nyc_days", "D"), ("nyc_total", "T")):
        v = h["models"][mdl]
        P = v["pooled"]
        dboth, fl = v["capped_minus_padding_both"], v["fleet_capped_minus_padding_both"]
        dfb = v["capped_with_fallback_minus_padding"]
        body.append(f"{labels[mdl]} & {f1(P['hgs_conservative'][0])} & {f1(v['capped_with_fallback_pooled'][0])} & "
                    f"{f1(dfb[0])} [{f1(dfb[1])}, {f1(dfb[2])}] & {f1(dboth[0])} [{f1(dboth[1])}, {f1(dboth[2])}] & "
                    f"{f2(fl[0])} & {v['certified']['hgs_conservative']} & {v['certified']['hgs_capped_cons']}\\\\")
        m.update({f"AmzH{tag}Pad": f1(P["hgs_conservative"][0]), f"AmzH{tag}CapFb": f1(v["capped_with_fallback_pooled"][0]),
                  f"AmzH{tag}FbDiff": f1(dfb[0]), f"AmzH{tag}FbDiffLo": f1(dfb[1]), f"AmzH{tag}FbDiffHi": f1(dfb[2]),
                  f"AmzH{tag}Both": str(v["both"]), f"AmzH{tag}BothDiff": f1(dboth[0]),
                  f"AmzH{tag}BothDiffLo": f1(dboth[1]), f"AmzH{tag}BothDiffHi": f1(dboth[2]),
                  f"AmzH{tag}Fleet": f2(fl[0]), f"AmzH{tag}CertPad": str(v["certified"]["hgs_conservative"]),
                  f"AmzH{tag}CertCap": str(v["certified"]["hgs_capped_cons"]), f"AmzH{tag}Fails": str(v["fails_certificate"]),
                  f"AmzH{tag}Admitted": str(v["admitted"])})
    a = h["models"]["assumed"]
    m.update({"AmzHRoutes": str(h["routes"]), "AmzHPadPlans": str(a["plans"]["hgs_conservative"]),
              "AmzHNotRun": str(a["screen_not_run"])})
    for mdl in h["models"].values():
        assert mdl["screen_not_run"] == a["screen_not_run"] and mdl["plans"]["hgs_conservative"] == a["plans"]["hgs_conservative"]
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{3.5pt}",
        r"\caption{The " + str(h["routes"]) + r" Amazon routes with the HGS solver (exploratory). \emph{Padding} and "
        r"\emph{Capped}: pooled validated reliability (\%) of 20\% padding and of the capped HGS procedure, which "
        r"falls back to padding on the " + str(a["screen_not_run"]) + r" routes where its scaling solves failed and the "
        r"screen could not run. \emph{All}: capped minus padding over all routes; \emph{Both}: the same on the routes "
        r"where the screen ran, with the difference in vehicles. \emph{Certified}: plans certified, padding and capped. "
        r"95\% bootstrap intervals.}",
        r"\label{tab:amazonhgs}",
        r"\begin{tabular}{@{}lccllccc@{}}", r"\toprule",
        r" & & & \multicolumn{2}{c}{Capped minus padding} & & \multicolumn{2}{c}{Certified}\\",
        r"\cmidrule(lr){4-5}\cmidrule(lr){7-8}",
        r"Delay model & Padding & Capped & All & Both & Vehicles & Pad. & Cap.\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    return table, m


def weights_outputs(ws, wb, hw=None):
    """Appendix table: the advantage of the original procedure over 20% padding under the weight vectors tried."""
    from weight_bracketing import WEIGHTS as WB
    run1 = (("baseline_rerun", "AHP (original)", (0.5693, 0.2643, 0.1055, 0.0609)),
            ("slack_first", "Slack first", (0.2643, 0.5693, 0.1055, 0.0609)),
            ("distance_heavy", "Distance heavy", (0.80, 0.10, 0.05, 0.05)),
            ("equal", "Equal", (0.25, 0.25, 0.25, 0.25)))
    run2 = (("original_here", "AHP (original)"), ("equal_here", "Equal"),
            ("fleet_up", "Vehicle weight raised"), ("duration_up", "Driver-time weight raised"))
    iv = lambda v: f"{f1(v[0])} [{f1(v[1])}, {f1(v[2])}]"  # noqa: E731
    wf = lambda w: ", ".join(f"{x:.4f}".rstrip("0").rstrip(".") for x in w)  # noqa: E731
    body = [r"\multicolumn{5}{@{}l}{\emph{First run}}\\"]
    for k, lab, w in run1:
        v = ws[k]
        body.append(rf"\quad {lab} & ({wf(w)}) & {v['selected']} & {f1(v['pooled_P_pp'])} & {iv(v['P_minus_C_pp'])}\\")
    body.append(r"\multicolumn{5}{@{}l}{\emph{Second run, another machine}}\\")
    for k, lab in run2:
        v = wb[k]
        body.append(rf"\quad {lab} & ({wf(WB[k])}) & {v['adm']} & {f1(v['pooled'])} & {iv(v['adv'])}\\")
    if hw is not None:
        e, d = hw["vectors"]["equal"], hw["vectors"]["duration_up"]
        body.append(r"\multicolumn{5}{@{}l}{\emph{Capped HGS procedure, " + str(e["common"]) + r" instances}}\\")
        body.append(rf"\quad AHP (original) & ({wf((0.5693, 0.2643, 0.1055, 0.0609))}) & {e['original_selected']} & "
                    rf"{f1(e['original_pooled'][0])} & {iv(e['original_minus_padding'])}\\")
        for v, lab in ((e, "Equal"), (d, "Driver-time weight raised")):
            body.append(rf"\quad {lab} & ({wf(v['weights'])}) & {v['selected']} & {f1(v['pooled'][0])} & {iv(v['minus_padding'])}\\")
    table = "\n".join([
        r"\begin{table}[h]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Sensitivity to the objective weights on the 53 development instances (exploratory). Weights in the "
        r"order distance, slack deficit, driver time, vehicles. \emph{Adm.}: instances where screening admitted a plan; "
        r"\emph{Pooled}: pooled validated reliability (\%) of the original procedure; \emph{Advantage}: its paired "
        r"advantage over 20\% padding in percentage points on the " + str(ws["equal"]["P_minus_C_common"]) +
        r" instances where padding has a plan, with 95\% bootstrap intervals. OR-Tools stops at a time limit, so "
        r"results are compared within a run; the two runs were made on different machines. Last block: the capped HGS "
        r"procedure (code/hgs\_weights.py) on the development instances where both it and padding have a plan; "
        r"HGS stops after a fixed number of iterations, so these rows do not depend on the machine.}",
        r"\label{tab:weights}",
        r"\begin{tabular}{@{}llccl@{}}", r"\toprule",
        r"Weights & Vector & Adm. & Pooled & Advantage\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    adv = [ws[k]["P_minus_C_pp"] for k, *_ in run1] + [wb[k]["adv"] for k, _ in run2]
    m = {"WgEqOneMean": f1(ws["equal"]["P_minus_C_pp"][0]), "WgEqOneLo": f1(ws["equal"]["P_minus_C_pp"][1]),
         "WgEqOneHi": f1(ws["equal"]["P_minus_C_pp"][2]),
         "WgEqTwoMean": f1(wb["equal_here"]["adv"][0]), "WgEqTwoLo": f1(wb["equal_here"]["adv"][1]),
         "WgEqTwoHi": f1(wb["equal_here"]["adv"][2]),
         "WgDurMean": f1(wb["duration_up"]["adv"][0]), "WgDurLo": f1(wb["duration_up"]["adv"][1]),
         "WgDurHi": f1(wb["duration_up"]["adv"][2]),
         "WgFleetMean": f1(wb["fleet_up"]["adv"][0]), "WgFleetLo": f1(wb["fleet_up"]["adv"][1]),
         "WgFleetHi": f1(wb["fleet_up"]["adv"][2]),
         "WgDistMean": f1(ws["distance_heavy"]["P_minus_C_pp"][0]), "WgDistLo": f1(ws["distance_heavy"]["P_minus_C_pp"][1]),
         "WgDistHi": f1(ws["distance_heavy"]["P_minus_C_pp"][2]),
         "WgSlackMean": f1(ws["slack_first"]["P_minus_C_pp"][0]),
         "WgLowMean": f1(min(a[0] for a in adv)), "WgHighMean": f1(max(a[0] for a in adv))}
    # the text assumes: equal weights include zero in the first run but not the second; driver-time-raised includes zero
    assert ws["equal"]["P_minus_C_pp"][1] < 0 < wb["equal_here"]["adv"][1] and wb["duration_up"]["adv"][1] < 0
    assert sum(a[1] < 0 for a in adv) == 2
    return table, m


def ablation_outputs(a):
    """HGS ablation: separate the weighted objective from the buffers and the screen."""
    C = a["configs"]
    rows = (("hgs_conservative", r"20\% padding (distance objective, padded speed)"),
            ("hgs_weighted_noscreen", r"Weighted objective, no buffer, no screen"),
            ("hgs_distance_capped", r"Distance objective, capped buffers, screened"),
            ("hgs_capped_cons", r"Capped procedure (weighted, capped buffers, screened)"))
    iv = lambda v: f"{f1(v[0])} [{f1(v[1])}, {f1(v[2])}]"  # noqa: E731
    body = []
    for k, lab in rows:
        v = C[k]
        if k == "hgs_conservative":
            body.append(f"{lab} & {f1(v['pooled_common'][0])} & -- & -- & -- & {v['certified_common']}\\\\")
        else:
            body.append(f"{lab} & {f1(v['pooled_common'][0])} & {iv(v['minus_padding'])} & "
                        f"{f2(v['fleet_minus_padding'][0])} & {f1(v['distance_pct_minus_padding'][0])} & "
                        f"{v['certified_common']}\\\\")
    n = a["common"]
    table = "\n".join([
        r"\begin{table}[t]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
        r"\caption{HGS ablation on the " + str(n) + r" synthetic instances of the development study and the second "
        r"confirmatory study where every configuration has a plan (exploratory). \emph{Pooled}: pooled validated "
        r"reliability (\%); \emph{Minus padding}: paired difference from 20\% padding in percentage points, with "
        r"95\% bootstrap intervals; \emph{Veh.} and \emph{Dist.}: mean difference from padding in vehicles and in "
        r"distance (\%); \emph{Cert.}: plans certified. The screened configurations share the buffer grid, the "
        r"screening days, the admission rule and the fallback to 20\% padding.}",
        r"\label{tab:ablation}",
        r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{5.6cm}clrrc@{}}", r"\toprule",
        r"Configuration & Pooled & Minus padding & Veh. & Dist. & Cert.\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    m = {"AbN": str(n), "AbInst": str(a["instances"]), "AbDistSel": str(a["distance_selected_common"])}
    for k, tag in (("hgs_conservative", "Pad"), ("hgs_weighted_noscreen", "W"), ("hgs_distance_capped", "D"),
                   ("hgs_capped_cons", "Full")):
        v = C[k]
        m[f"Ab{tag}Pooled"] = f1(v["pooled_common"][0])
        m[f"Ab{tag}Cert"] = str(v["certified_common"])
        if k != "hgs_conservative":
            for j, s in enumerate(("", "Lo", "Hi")):
                m[f"Ab{tag}Diff{s}"] = f1(v["minus_padding"][j])
            m[f"Ab{tag}Fleet"] = f2(v["fleet_minus_padding"][0])
            m[f"Ab{tag}Dist"] = f1(v["distance_pct_minus_padding"][0])
    for key, tag in (("full_minus_distance_capped", "FullD"), ("full_minus_weighted_noscreen", "FullW")):
        for j, s in enumerate(("", "Lo", "Hi")):
            m[f"Ab{tag}{s}"] = f1(a[key][j])
    full, dist = C["hgs_capped_cons"], C["hgs_distance_capped"]
    m["AbFullDFleetAbs"] = f2(dist["fleet_minus_padding"][0] - full["fleet_minus_padding"][0])
    # the text assumes: screening with either objective beats padding; the two screened versions are level;
    # the weighted plan without screening is worse than padding; the weighted objective uses fewer vehicles
    assert dist["minus_padding"][1] > 0 and full["minus_padding"][1] > 0
    assert a["full_minus_distance_capped"][1] < 0 < a["full_minus_distance_capped"][2]
    assert C["hgs_weighted_noscreen"]["minus_padding"][2] < 0
    assert full["fleet_minus_padding"][0] < dist["fleet_minus_padding"][0]
    return table, m


def fixed_order_macros(fo):
    t = fo["total"]
    fl, di = t["fleet_fixed_minus_procedure"], t["distance_pct_fixed_minus_procedure"]
    m = {"FoInst": str(t["instances"]), "FoProc": str(t["procedure_certified"]), "FoFixed": str(t["fixed_order_certified"]),
         "FoFixedOnly": str(t["fixed_only"]), "FoProcOnly": str(t["procedure_only"]), "FoBoth": str(t["both"]),
         "FoFails": str(t["fresh_fails"]), "FoBelow": str(t["fresh_below_target"]),
         "FoFleet": f2(fl[0]), "FoFleetLo": f2(fl[1]), "FoFleetHi": f2(fl[2]),
         "FoDist": f2(di[0]), "FoDistLo": f2(di[1]), "FoDistHi": f2(di[2])}
    # reductions, for wording such as "0.05 fewer vehicles [-0.01, 0.11]"
    m.update({"FoFleetLess": f2(-fl[0]), "FoFleetLessLo": f2(-fl[2]), "FoFleetLessHi": f2(-fl[1]),
              "FoDistLess": f2(-di[0]), "FoDistLessLo": f2(-di[2]), "FoDistLessHi": f2(-di[1])})
    assert fl[0] < 0 and di[0] < 0
    # the text assumes: more certified, no fresh failures, cost differences indistinguishable from zero
    assert t["fixed_order_certified"] > t["procedure_certified"] and t["fresh_fails"] == 0
    assert fl[1] < 0 < fl[2] and di[1] < 0 < di[2]
    return m


def hgs_weights_macros(h):
    m = {}
    for name, tag in (("equal", "Eq"), ("duration_up", "Dur")):
        v = h["vectors"][name]
        for key, short in (("minus_padding", "Pad"), ("minus_original_weights", "Orig"),
                           ("fleet_minus_original_weights", "Fleet"), ("original_minus_padding", "OrigPad")):
            fmt = f2 if short == "Fleet" else f1
            for j, s in enumerate(("", "Lo", "Hi")):
                m[f"Hw{tag}{short}{s}"] = fmt(v[key][j])
        m[f"Hw{tag}N"] = str(v["common"])
        m[f"Hw{tag}Pooled"] = f1(v["pooled"][0])
        assert v["minus_padding"][1] > 10        # the text: the capped HGS procedure stays well ahead of padding
    return m


LADE_NAMES = {"jl": "Jilin", "sh": "Shanghai", "hz": "Hangzhou", "cq": "Chongqing", "yt": "Yantai"}


def lade_outputs(F):
    pct = lambda x: f1(100 * x)  # noqa: E731
    rs, gps = F["replay_shuffle"], F["gps"]
    body = []
    for c in ("hz", "cq", "yt", "sh", "jl"):
        r, g = rs[f"{c}_traj"], gps[c]
        body.append(f"{LADE_NAMES[c]} & {r['courier_days']} & {pct(r['observed_late'])} & {pct(r['replay_late'])} & "
                    f"{pct(r['shuffled_late'])} & {pct(g['direct_share'])} & {g['history']['pace_median']:.3f} & "
                    f"{g['future']['pace_median']:.3f} & {g['history']['still_median'] / 60:.1f} & "
                    f"{g['future']['still_median'] / 60:.1f}\\\\")
    table = "\n".join([
        r"\begin{table}[h!]", r"\centering", r"\small", r"\setlength{\tabcolsep}{3.5pt}",
        r"\caption{Real pickup operations in five Chinese cities, 21 March to 20 April 2022 (LaDe; exploratory). "
        r"Left: busy courier-days (at least " + str(F["busy"]) + r" pickups) and the share (\%) with a pickup after "
        r"its promised window: observed, replayed with the courier's real gaps between pickups in the real order, and "
        r"with the same gaps in random order (mean of " + str(F["shuffles"]) + r" permutations). Right: direct trips "
        r"between consecutive pickups measured from GPS, their share of all trips (\%), and the median pace (seconds of "
        r"movement per metre) and median time stationary (minutes) in the first 21 days (\emph{H}) and the last 10 "
        r"(\emph{F}). Shanghai was under lockdown for most of the period.}",
        r"\label{tab:lade}",
        r"\begin{tabular}{@{}lrrrrrcccc@{}}", r"\toprule",
        r" & \multicolumn{4}{c}{Lateness of real routes} & \multicolumn{5}{c}{Direct trips (GPS)}\\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-10}",
        r" & & & & & & \multicolumn{2}{c}{Pace} & \multicolumn{2}{c}{Stationary}\\",
        r"\cmidrule(lr){7-8}\cmidrule(lr){9-10}",
        r"City & Days & Obs. & Replay & Shuffled & Share & H & F & H & F\\", r"\midrule",
        *body, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    allr = list(rs.values())
    m = {"LfCourierDays": f"{sum(r['courier_days'] for r in allr):,}".replace(",", "{,}"),
         "LfShuMin": pct(min(r["shuffled_late"] for r in allr)), "LfShuMax": pct(max(r["shuffled_late"] for r in allr)),
         "LfObsMin": pct(min(r["observed_late"] for r in allr)), "LfObsMax": pct(max(r["observed_late"] for r in allr)),
         "LfJlMainDays": str(rs["jl_main"]["courier_days"]), "LfJlMainObs": pct(rs["jl_main"]["observed_late"]),
         "LfJlMainShu": pct(rs["jl_main"]["shuffled_late"]),
         "LfShMainDays": str(rs["sh_main"]["courier_days"]), "LfShMainObs": pct(rs["sh_main"]["observed_late"]),
         "LfShMainShu": pct(rs["sh_main"]["shuffled_late"]),
         "LfLogsN": str(F["logs_model"]["courier_days"]), "LfLogsPred": pct(F["logs_model"]["predicted_late"]),
         "LfLogsObs": pct(F["logs_model"]["observed_late"]),
         "LfDaysZero": str(F["days_needed"]["failures_0"]), "LfDaysOne": str(F["days_needed"]["failures_1"]),
         "LfDaysTwo": str(F["days_needed"]["failures_2"]), "LfBoundTwentyOne": f"{F['days_needed']['bound_21_of_21']:.3f}",
         "LfDirectMin": pct(min(g["direct_share"] for g in gps.values())),
         "LfDirectMax": pct(max(g["direct_share"] for g in gps.values())),
         "LfDirectLegs": str(sum(g["direct_legs"] for g in gps.values())),
         "LfSpeedHz": f"{gps['hz']['speed_ms_median']:.1f}"}
    for c, tag in (("yt", "Yt"), ("hz", "Hz")):
        t = F["teams"][c]
        m[f"LfTeams{tag}"] = str(t["teams"])
        m[f"LfInfeas{tag}"] = pct(t["infeasible_share"])
        m[f"LfEarly{tag}"] = pct(t["early_pickup_share"])
        m[f"LfLate{tag}"] = pct(t["late_pickup_share"])
    # the text assumes: the replay reproduces the observed lateness exactly; shuffling makes most routes late;
    # the logs model overpredicts lateness by an order of magnitude
    assert all(abs(r["replay_late"] - r["observed_late"]) < 1e-12 for r in allr)
    assert min(r["shuffled_late"] for r in allr) > 0.5
    assert F["logs_model"]["predicted_late"] > 10 * F["logs_model"]["observed_late"]
    # "barely moved": median pace and still time within 6% between the two periods in every city
    for g in gps.values():
        for k in ("pace_median", "still_median"):
            assert abs(g["future"][k] / g["history"][k] - 1) < 0.06, (k, g)
    m["LfPaceMaxChange"] = f1(100 * max(abs(g["future"]["pace_median"] / g["history"]["pace_median"] - 1)
                                     for g in gps.values()))
    m["LfStillMaxChange"] = f1(100 * max(abs(g["future"]["still_median"] / g["history"]["still_median"] - 1)
                                      for g in gps.values()))
    return table, m


def margin_macros(sm):
    rows = sm["rows"]
    mg = np.array([r["margin"] for r in rows])
    inc, pk = sm["incidents"], sm["strong_peak"]
    band = lambda d, k: d["by_margin"][k]  # noqa: E731
    lo, mid, hi1, hi2 = "0.000-0.050", "0.050-0.100", "0.100-0.167", "0.167-0.250"
    high_n = band(inc, hi1)[0] + band(inc, hi2)[0] + band(inc, "0.250-9.000")[0]
    high_all = sum(all(r["survives"].values()) for r in rows if r["margin"] >= 0.10 - 1e-12)
    m = {"SmPlans": str(sm["plans"]), "SmMedian": f1(100 * float(np.median(mg))),
         "SmZeroShare": str(round(100 * float((mg == 0).mean()))), "SmZero": str(int((mg == 0).sum())),
         "SmLowN": str(band(inc, lo)[0]), "SmLowInc": str(band(inc, lo)[1]), "SmLowPeak": str(band(pk, lo)[1]),
         "SmMidN": str(band(inc, mid)[0]), "SmMidInc": str(band(inc, mid)[1]), "SmMidPeak": str(band(pk, mid)[1]),
         "SmHighN": str(high_n), "SmHighAll": str(high_all),
         "SmCovered": str(pk["covered"]), "SmCoveredSurv": str(pk["covered_survived"]),
         "SmAucInc": f"{inc['auc_margin']:.2f}", "SmAucPeak": f"{pk['auc_margin']:.2f}",
         "SmAucValInc": f"{inc['auc_validated']:.2f}", "SmAucValPeak": f"{pk['auc_validated']:.2f}"}
    # the text assumes: every plan with margin >= 10% survived every harsher model; the success estimate
    # predicts survival at least as well as the margin; every plan covered by the strong-peak guarantee survived
    assert high_all == high_n and inc["auc_validated"] >= inc["auc_margin"] - 0.01 and pk["covered_survived"] == pk["covered"]
    return m


def _frac(x):
    from fractions import Fraction
    q = Fraction(float(x)).limit_denominator(9)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def search_macros(s):
    m = {"SrchSeconds": str(int(s["seconds_per_attempt"])),
         "SrchNomMissing": str(s["nominal_missing"]), "SrchNomFound": str(s["nominal_found"]),
         "SrchConsMissing": str(s["conservative_missing"]), "SrchConsFound": str(s["conservative_found"])}
    for delay, tag in (("assumed", ""), ("nyc_days", "D"), ("nyc_total", "T")):
        r = s[f"padding_rescored_{delay}"]
        d = r["capped_minus_padding"]
        m.update({f"Srch{tag}Pad": f1(r["padding_pooled"]), f"Srch{tag}Diff": f1(d[0]),
                  f"Srch{tag}DiffLo": f1(d[1]), f"Srch{tag}DiffHi": f1(d[2])})
    return m


def main():
    OUT.mkdir(exist_ok=True)
    for f in SHARED:
        shutil.copy(ROOT / "paper_nhsjs" / f, OUT / f)
    # define every abbreviation in the copied captions (Table~\ref{tab:configs} defines the configurations)
    fixes = {"tab_paired.tex": ("SC denotes screened conservative speed with its prespecified fallback.",
                                "C: 20\\% padding; S: the slack-aware plan (weighted objective, no buffer, no "
                                "screening); P: the original procedure; SC: screened conservative "
                                "(Table~\\ref{tab:configs})."),
             "tab_gh.tex": ("instances where the anchor solves found a plan",
                            "instances where the four single-criterion solves that set the objective's scaling "
                            "ranges (the anchors) all found a plan")}
    for f, (old, new) in fixes.items():
        t = (OUT / f).read_text()
        assert t.count(old) == 1, f
        (OUT / f).write_text(t.replace(old, new))
    c = json.loads((ROOT / "results/certify_summary.json").read_text())
    global CAP_CERT_DEV
    CAP_CERT_DEV = c["studies"]["development"]["capped_procedure"]["certified"]
    fr = json.loads((ROOT / "results/frontier_summary.json").read_text())
    w = json.loads((ROOT / "results/wrong_model_summary.json").read_text())
    t1, m = certify_table(c)
    t2, m2 = frontier_outputs(fr)
    t3, m3 = wrong_outputs(w)
    m.update(m2)
    m.update(m3)
    from certify import cp_lower
    m["CertMinSuccesses"] = str(next(k for k in range(5001) if cp_lower(k, 5000) >= 0.95))
    resc = json.loads((ROOT / "results/misspecification_rescreen.json").read_text())["summary"]
    for mdl, tag in (("incidents", "Inc"), ("strong_peak", "Peak")):
        m[f"Wr{tag}Pad"] = f"{resc[mdl]['ort_conservative']['mean']:.1f}"
        m[f"Wr{tag}PadN"] = str(resc[mdl]["ort_conservative"]["instances"])
    st_table, st_m = stress_outputs(json.loads((ROOT / "results/stress_certify_summary.json").read_text()))
    (OUT / "tab_stress.tex").write_text(st_table)
    m.update(st_m)
    hp = ROOT / "results/amazon_hgs_summary.json"
    if hp.exists():
        ht, hm = amazon_hgs_outputs(json.loads(hp.read_text()))
        (OUT / "tab_amazon_hgs.tex").write_text(ht)
        m.update(hm)
    pf = json.loads((ROOT / "results/padding_feasibility.json").read_text())
    m.update({"PfMissing": str(pf["missing_total"]), "PfProven": str(pf["proven_total"]),
              "PfFiftyMissing": str(pf["levels"]["50"]["missing"]), "PfFiftyProven": str(pf["levels"]["50"]["proven_infeasible"]),
              "PfTwentyMissing": str(pf["levels"]["20"]["missing"]), "PfTwentyProven": str(pf["levels"]["20"]["proven_infeasible"]),
              "PfUnresolved": str(pf["missing_total"] - pf["proven_total"])})
    sc = ROOT / "results/amazon_search_check.json"
    if sc.exists():
        m.update(search_macros(json.loads(sc.read_text())))
    lf = ROOT / "results/lade_findings.json"
    if lf.exists():
        lt_, lm = lade_outputs(json.loads(lf.read_text()))
        (OUT / "tab_lade.tex").write_text(lt_)
        m.update(lm)
    hw = ROOT / "results/hgs_weights_summary.json"
    if hw.exists():
        m.update(hgs_weights_macros(json.loads(hw.read_text())))
    smp = ROOT / "results/slowdown_margin_summary.json"
    if smp.exists():
        m.update(margin_macros(json.loads(smp.read_text())))
    fo = ROOT / "results/fixed_order_summary.json"
    if fo.exists():
        m.update(fixed_order_macros(json.loads(fo.read_text())))
    ab = ROOT / "results/hgs_ablation_summary.json"
    if ab.exists():
        at, am = ablation_outputs(json.loads(ab.read_text()))
        (OUT / "tab_ablation.tex").write_text(at)
        m.update(am)
    hwp = ROOT / "results/hgs_weights_summary.json"
    wt, wm = weights_outputs(json.loads((ROOT / "results/weight_sensitivity_summary.json").read_text()),
                             json.loads((ROOT / "results/weight_bracketing_summary.json").read_text()),
                             json.loads(hwp.read_text()) if hwp.exists() else None)
    (OUT / "tab_weights.tex").write_text(wt)
    m.update(wm)
    from ahp_weights import A, main as _ahp  # noqa: F401
    rows = [" & ".join(_frac(x) for x in row) for row in A]
    (OUT / "tab_ahp.tex").write_text("\n".join([
        r"\begin{tabular}{@{}lcccc@{}}", r"\toprule",
        r" & Distance & Slack deficit & Driver time & Vehicles\\", r"\midrule",
        *[f"{lab} & {r}\\\\" for lab, r in zip(("Distance", "Slack deficit", "Driver time", "Vehicles"), rows)],
        r"\bottomrule", r"\end{tabular}", ""]))
    (OUT / "tab_certify.tex").write_text(t1)
    (OUT / "tab_frontier.tex").write_text(t2)
    (OUT / "tab_wrong.tex").write_text(t3)
    (OUT / "result_macros_ijss.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    print("ijss tables ok", len(m), "macros")


if __name__ == "__main__":
    main()
