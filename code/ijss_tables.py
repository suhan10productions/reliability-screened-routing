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
    rows = [("conservative", "20\\% padding (OR-Tools)"), ("procedure", "Original procedure"),
            ("capped_procedure", "Capped procedure"), ("screened_conservative", "Screened conservative"),
            ("hgs_conservative", "20\\% padding (HGS)"), ("hgs_capped_cons", "Capped procedure (HGS)")]
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
    return table, m


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
        r"Clopper--Pearson lower bound, rather than the estimate, must reach 95\%; because the plan is chosen on the "
        r"same days, this row is descriptive and is not a certificate in the sense of Theorem~\ref{thm:cert}.}",
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
        m.update({f"Wr{tag}Kept": str(c["kept"]), f"Wr{tag}Cert": str(c["certified"]), f"Wr{tag}Serv": f1(c["mean_service"]),
                  f"Wr{tag}HKept": str(h["kept"]), f"Wr{tag}HCert": str(h["certified"]), f"Wr{tag}HServ": f1(h["mean_service"])})
    return table, m


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
    sc = ROOT / "results/amazon_search_check.json"
    if sc.exists():
        m.update(search_macros(json.loads(sc.read_text())))
    (OUT / "tab_certify.tex").write_text(t1)
    (OUT / "tab_frontier.tex").write_text(t2)
    (OUT / "tab_wrong.tex").write_text(t3)
    (OUT / "result_macros_ijss.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    print("ijss tables ok", len(m), "macros")


if __name__ == "__main__":
    main()
