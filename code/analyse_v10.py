"""Manuscript text, tables, macros and Fig. 2 for the exploratory robust comparison.

Reads results/robust_dev and results/robust_capped_dev (robust plans), results/v7
(OR-Tools configurations) and results/hgs_dev (HGS configurations). Every plan of
an instance was validated on the same 5000-scenario bank (seed 400000 + seed),
so all comparisons are paired. A configuration without a plan scores 0. The
script checks that every record is present and complete before it computes
anything. Writes paper/result_macros_v10.tex, paper/robust_results.tex,
paper/robust_appendix.tex and paper/Fig2.pdf / Fig2.eps.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

from analyse_robust import boot, screened_robust

from study_robust import ITERATIONS

ROOT = Path(__file__).resolve().parents[1]
SIZES = (20, 50, 100)
SEEDS = {20: range(7200, 7220), 50: range(7500, 7515), 100: range(8000, 8010)}
DELTAS = (0.2, 0.4, 0.6)
GAMMAS = (1, 2, 3, 5, "box")


def f1(x):
    return f"{x:.1f}".replace("-", "$-$")


def f2(x):
    return f"{x:.2f}".replace("-", "$-$")


def iv(m):
    return f"{f1(m[0])} [{f1(m[1])}, {f1(m[2])}]"


def key(g, d):
    return f"{'box' if g == 'box' else 'G' + str(g)}_d{d:g}"


def load(directory):
    out = {}
    for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        out[r["instance_seed"]] = r
    return out


def validate(rob, cap, ort, hgs):
    seeds = [s for n in SIZES for s in SEEDS[n]]
    for name, d in (("robust_dev", rob), ("robust_capped_dev", cap)):
        assert sorted(d) == seeds, f"{name}: wrong seed set"
        assert not glob.glob(str(ROOT / "results" / name / "software_error_*.json")), f"{name}: software errors"
    for s in seeds:
        assert s in ort and s in hgs, f"missing OR-Tools or HGS record for {s}"
        for d, capped in ((rob[s], False), (cap[s], True)):
            assert d["schema"] == "relscreen-robust-1" and d["validation_seed"] == 400_000 + s
            assert d["validation_scenarios"] == 5000 and d["screen_scenarios"] == 1000
            assert d.get("capped", False) is capped
            assert d["search_seed"] == s and d["iterations"] == ITERATIONS[d["customers"]]
            expect = ([] if capped else [key(0, 0.0)]) + [key(g, x) for x in DELTAS for g in GAMMAS]
            assert d["grid"] == expect and set(d["settings"]) == set(expect)
            for v in d["settings"].values():
                assert (v["status"] == "ok") == (v["plan"] is not None)
                if v["plan"] is not None:
                    assert v["validation"]["scenarios"] == 5000
                    visits = sorted(c for r in v["plan"]["routes"] for c in r if c)
                    assert visits == list(range(1, d["customers"] + 1))
        assert ort[s]["validation_seed"] == 400_000 + s
    return seeds


def serv(e):
    return 0.0 if e is None or e.get("validation") is None else 100 * e["validation"]["service_level_success"]


def dist(e):
    return None if e is None or e.get("plan") is None else e["plan"]["metrics"]["distance"]


def fleet(e):
    return None if e is None or e.get("plan") is None else e["plan"]["metrics"]["fleet"]


def main():
    rob, cap, ort, hgs = (load("results/robust_dev"), load("results/robust_capped_dev"),
                          load("results/v7"), load("results/hgs_dev"))
    seeds = validate(rob, cap, ort, hgs)
    for s in seeds:
        h = hgs[s]
        assert h["validation_seed"] == 400_000 + s and h["validation_scenarios"] == 5000, f"HGS bank {s}"
    n_of = {s: rob[s]["customers"] for s in seeds}

    def cfg(s, c):
        kind, _, name = c.partition(":")
        if kind == "rob":
            return rob[s]["settings"][name]
        if kind == "cap":
            return cap[s]["settings"][name]
        if kind == "ort":
            return ort[s]["configurations"][name]
        if kind == "hgs":
            return hgs[s]["configurations"][name]
        if c == "screened":
            return screened_robust(rob[s]["settings"])[0]
        if c == "screened_cap":
            return screened_robust(cap[s]["settings"])[0]
        raise KeyError(c)

    nominal = {s: dist(rob[s]["settings"][key(0, 0.0)]) for s in seeds}

    def stats(c, members):
        es = [cfg(s, c) for s in members]
        withp = [s for s, e in zip(members, es) if dist(e) is not None]
        return {"plans": len(withp), "service": float(np.mean([serv(e) for e in es])),
                "distance": float(np.mean([100 * (dist(cfg(s, c)) / nominal[s] - 1) for s in withp])) if withp else None,
                "fleet": float(np.mean([fleet(cfg(s, c)) for s in withp])) if withp else None}

    def paired(a, b, members=None):
        members = seeds if members is None else members
        sd = [serv(cfg(s, a)) - serv(cfg(s, b)) for s in members]
        both = [s for s in members if dist(cfg(s, a)) is not None and dist(cfg(s, b)) is not None]
        dd = [100 * (dist(cfg(s, a)) / dist(cfg(s, b)) - 1) for s in both]
        fd = [fleet(cfg(s, a)) - fleet(cfg(s, b)) for s in both]
        return {"service": boot(sd), "distance": boot(dd), "fleet": boot(fd), "both": len(both)}

    th = "\\theta"
    rows_main = [
        ("Conservative speed (OR-Tools)", "ort:conservative"),
        ("Capped procedure (OR-Tools)", "ort:capped_procedure"),
        ("Capped procedure, conservative fallback (HGS)", "hgs:hgs_capped_cons"),
        (f"Robust, box, ${th}=0.4$", "rob:box_d0.4"),
        (f"Robust, box, ${th}=0.6$", "rob:box_d0.6"),
        (f"Relief, $\\Gamma=3$, ${th}=0.4$", "cap:G3_d0.4"),
        (f"Relief, box, ${th}=0.4$", "cap:box_d0.4"),
        (f"Relief, $\\Gamma=3$, ${th}=0.6$", "cap:G3_d0.6"),
        (f"Relief, box, ${th}=0.6$", "cap:box_d0.6"),
        ("Screened robust", "screened"),
        ("Screened robust with relief", "screened_cap"),
    ]
    table = {}
    for label, c in rows_main:
        table[c] = {"all": stats(c, seeds), **{n: stats(c, [s for s in seeds if n_of[s] == n]) for n in SIZES}}

    # every grid setting, for the appendix and the figure
    grid = {}
    for variant in ("rob", "cap"):
        for d in DELTAS:
            for g in GAMMAS:
                c = f"{variant}:{key(g, d)}"
                grid[c] = {"all": stats(c, seeds), **{n: stats(c, [s for s in seeds if n_of[s] == n]) for n in SIZES}}

    contrasts = [
        (f"Relief minus standard, box, ${th}=0.4$", "cap:box_d0.4", "rob:box_d0.4"),
        (f"Relief, $\\Gamma=3$, ${th}=0.4$, minus OR-Tools capped procedure", "cap:G3_d0.4", "ort:capped_procedure"),
        (f"Relief, $\\Gamma=3$, ${th}=0.4$, minus HGS capped procedure", "cap:G3_d0.4", "hgs:hgs_capped_cons"),
        (f"Relief, $\\Gamma=3$, ${th}=0.6$, minus HGS capped procedure", "cap:G3_d0.6", "hgs:hgs_capped_cons"),
        ("Screened robust with relief minus HGS capped procedure", "screened_cap", "hgs:hgs_capped_cons"),
        (f"Screened robust with relief minus relief, box, ${th}=0.6$", "screened_cap", "cap:box_d0.6"),
    ]
    con = {(a, b): paired(a, b) for _, a, b in contrasts}
    both_box = [s for s in seeds if dist(cfg(s, "rob:box_d0.4")) is not None]
    same_box = sum(cfg(s, "rob:box_d0.4")["plan"]["routes"] == cfg(s, "cap:box_d0.4")["plan"]["routes"] for s in both_box)
    adm_cap = sum(screened_robust(cap[s]["settings"])[1] for s in seeds)
    adm_rob = sum(screened_robust(rob[s]["settings"])[1] for s in seeds)
    noplan = {d: sum(dist(cfg(s, f"rob:box_d{d:g}")) is None for s in seeds) for d in DELTAS}
    relieved, explained = {}, {}
    from relscreen_v6 import ModelParams, make_synthetic_instance
    from robust_generator import CappedRobustModel
    p = ModelParams()
    for d in DELTAS:
        blocked = set()
        for s in seeds:
            data = make_synthetic_instance(n_of[s], ort[s]["vehicles_available"], s)
            if CappedRobustModel(data, p, None, d).relieved:
                blocked.add(s)
        missing = {s for s in seeds if dist(cfg(s, f"rob:box_d{d:g}")) is None}
        relieved[d] = len(blocked)
        explained[d] = missing == blocked
    same_fail = all({s for s in seeds if dist(cfg(s, f"rob:{key(g, d)}")) is None}
                    == {s for s in seeds if dist(cfg(s, f"rob:box_d{d:g}")) is None}
                    for d in DELTAS for g in GAMMAS)
    ort_nom = float(np.mean([100 * (dist(cfg(s, "ort:nominal")) / nominal[s] - 1) for s in seeds]))
    bench = json.loads((ROOT / "results/robust_benchmark.json").read_text())
    gaps = {n: [100 * (b[f"r{ITERATIONS[n]}"] / b["hgs"] - 1) for b in bench if b["n"] == n] for n in SIZES}
    assert all(len(gaps[n]) == len(SEEDS[n]) for n in SIZES)
    equal20 = sum(abs(x) < 1e-9 for x in gaps[20])

    T = lambda c: table[c]["all"]
    C = lambda a2, b2, f="service", k=0: con[(a2, b2)][f][k]
    macros = {
        "RobInstances": str(len(seeds)),
        "RobNoPlanBoxFour": str(noplan[0.4]), "RobNoPlanBoxSix": str(noplan[0.6]),
        "RobBoxFourP": f1(T("rob:box_d0.4")["service"]), "RobBoxSixP": f1(T("rob:box_d0.6")["service"]),
        "RobCapGThreeFourP": f1(T("cap:G3_d0.4")["service"]), "RobCapBoxFourP": f1(T("cap:box_d0.4")["service"]),
        "RobCapGThreeSixP": f1(T("cap:G3_d0.6")["service"]), "RobCapBoxSixP": f1(T("cap:box_d0.6")["service"]),
        "RobScreenedP": f1(T("screened")["service"]), "RobScreenedCapP": f1(T("screened_cap")["service"]),
        "RobScreenedCapAdm": str(adm_cap), "RobScreenedAdm": str(adm_rob),
        "RobOrtCappedP": f1(T("ort:capped_procedure")["service"]), "RobHgsCappedP": f1(T("hgs:hgs_capped_cons")["service"]),
        "RobOrtNominalD": f1(ort_nom),
        "RobReliefGain": f1(C("cap:box_d0.4", "rob:box_d0.4")),
        "RobCapGThreeFourMinusOrt": f1(C("cap:G3_d0.4", "ort:capped_procedure")),
        "RobCapGThreeFourMinusOrtLo": f1(C("cap:G3_d0.4", "ort:capped_procedure", k=1)),
        "RobCapGThreeFourMinusOrtHi": f1(C("cap:G3_d0.4", "ort:capped_procedure", k=2)),
        "RobCapGThreeFourMinusOrtFleet": f2(C("cap:G3_d0.4", "ort:capped_procedure", "fleet")),
        "RobCapGThreeSixMinusHgs": f1(C("cap:G3_d0.6", "hgs:hgs_capped_cons")),
        "RobCapGThreeSixMinusHgsLo": f1(C("cap:G3_d0.6", "hgs:hgs_capped_cons", k=1)),
        "RobCapGThreeSixMinusHgsHi": f1(C("cap:G3_d0.6", "hgs:hgs_capped_cons", k=2)),
        "RobCapGThreeSixMinusHgsFleet": f2(C("cap:G3_d0.6", "hgs:hgs_capped_cons", "fleet")),
        "RobScreenedCapMinusHgs": f1(C("screened_cap", "hgs:hgs_capped_cons")),
        "RobScreenedCapMinusHgsLo": f1(C("screened_cap", "hgs:hgs_capped_cons", k=1)),
        "RobScreenedCapMinusHgsHi": f1(C("screened_cap", "hgs:hgs_capped_cons", k=2)),
        "RobScreenedCapMinusHgsFleet": f2(C("screened_cap", "hgs:hgs_capped_cons", "fleet")),
        "RobBenchEqualTwenty": str(equal20), "RobBenchCountTwenty": str(len(gaps[20])),
        "RobBenchGapFifty": f"{np.mean(gaps[50]):.2f}", "RobBenchGapHundred": f1(np.mean(gaps[100])),
        "RobItersSmall": str(ITERATIONS[20]), "RobItersHundred": str(ITERATIONS[100]),
    }
    assert ITERATIONS[20] == ITERATIONS[50]
    (ROOT / "paper/result_macros_v10.tex").write_text(
        "\n".join("\\newcommand{\\" + k + "}{" + v + "}" for k, v in macros.items()) + "\n")

    def tab(caption, label, cols, header, rows, size="footnotesize", pre=None):
        return "\n".join([r"\begin{table}[htbp]", r"\centering", f"\\{size}", *(pre or []),
                          f"\\caption{{{caption}}}", f"\\label{{{label}}}", f"\\begin{{tabular}}{{{cols}}}",
                          r"\toprule", header + r"\\", r"\midrule", *[r + r"\\" for r in rows],
                          r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])

    main_rows = []
    for label, c in rows_main:
        x = table[c]
        main_rows.append(f"{label} & {x['all']['plans']} & " + " & ".join(f1(x[n]['service']) for n in SIZES)
                         + f" & {f1(x['all']['service'])} & {f1(x['all']['distance'])} & {f2(x['all']['fleet'])}")
    con_rows = []
    for label, a2, b2 in contrasts:
        v = con[(a2, b2)]
        con_rows.append(f"{label} & {iv(v['service'])} & {iv(v['distance'])} & {f2(v['fleet'][0])}")

    box2 = grid["rob:box_d0.2"]["all"]
    g3_4h, g3_6h = ("cap:G3_d0.4", "hgs:hgs_capped_cons"), ("cap:G3_d0.6", "hgs:hgs_capped_cons")
    text = [
        r"\subsection{Robust optimization comparator}\label{sec:robust}", "",
        f"Table~\\ref{{tab:robust}} compares the robust plans with the screened procedures on the {len(seeds)} "
        f"development instances with 20, 50 and 100 customers, and Fig.~\\ref{{fig:robust}} shows the trade-off "
        f"between service and distance; the appendix lists every setting. Every distance, including those of the "
        f"OR-Tools and HGS plans, is given relative to the nominal plan found by the robust search with $\\Gamma=0$; "
        f"the OR-Tools nominal plans are {f1(ort_nom)}\\% longer on average.", "",
        tab("Robust comparator on the " + str(len(seeds)) + " development instances (exploratory): number of instances "
            "with a plan, mean validated service-event probability (\\%) by size and pooled, mean distance relative to the "
            "nominal plan of the robust search ($\\Gamma=0$) and mean vehicles, both over instances with a plan. A missing "
            "plan scores zero. Relief denotes the robust model with reachability relief.",
            "tab:robust", r"@{}>{\raggedright\arraybackslash}p{4.6cm}rrrrrrr@{}",
            r"Configuration & Plans & $n=20$ & $n=50$ & $n=100$ & Pooled & Dist. (\%) & Veh.", main_rows),
        f"The standard robust model fails on the larger instances. Under box uncertainty it has no robust plan on "
        f"{noplan[0.4]} of the {len(seeds)} instances with ${th}=0.4$ and on {noplan[0.6]} with ${th}=0.6$. "
        + (f"These are exactly the instances on which some customer cannot be served on time even by a direct trip "
           f"at its upper travel time, so no fleet size helps. "
           if explained[0.4] and explained[0.6] else
           f"On most of them some customer cannot be served on time even by a direct trip at its upper travel time. ")
        + ("Every smaller budget $\\Gamma$ failed on exactly the same instances. " if same_fail else "")
        + f"This is the reachability obstruction that capped contraction addresses (Section~\\ref{{sec:capping}}). "
        f"The mildest box setting, ${th}=0.2$, the robust counterpart of conservative speed, still had no plan on "
        f"{len(seeds) - box2['plans']} instances and pooled {f1(box2['service'])}\\%.", "",
        f"Reachability relief removes the obstruction. Every relieved setting has a plan on all {len(seeds)} "
        f"instances, and under box uncertainty with ${th}=0.4$ relief raised pooled service by "
        f"{f1(C('cap:box_d0.4', 'rob:box_d0.4'))} points (Table~\\ref{{tab:robust-contrasts}}). "
        + (f"On the {len(both_box)} instances where the standard model had a plan, the two models returned the same "
           f"routes, so the whole gain comes from the instances without a standard robust plan. "
           if same_box == len(both_box) else
           f"On {same_box} of the {len(both_box)} instances where the standard model had a plan, the two models "
           f"returned the same routes. ")
        + f"The relieved robust plans then compete with the screened procedures. With $\\Gamma=3$ and ${th}=0.4$ they "
        f"exceeded the OR-Tools capped procedure by {f1(C('cap:G3_d0.4', 'ort:capped_procedure'))} points on average, "
        f"with an interval from {f1(C('cap:G3_d0.4', 'ort:capped_procedure', k=1))} to "
        f"{f1(C('cap:G3_d0.4', 'ort:capped_procedure', k=2))}, and used "
        f"{f2(C('cap:G3_d0.4', 'ort:capped_procedure', 'fleet'))} more vehicles per instance. Against the HGS capped "
        f"procedure the protection level decides the comparison. With $\\Gamma=3$, the ${th}=0.4$ setting was "
        f"{f1(-C(*g3_4h))} points less reliable (interval {f1(C(*g3_4h, k=1))} to {f1(C(*g3_4h, k=2))}), with "
        f"{f1(-C(*g3_4h, 'distance'))}\\% less distance and {f2(C(*g3_4h, 'fleet'))} more vehicles, while the ${th}=0.6$ setting "
        f"was {f1(C(*g3_6h))} points more reliable (interval {f1(C(*g3_6h, k=1))} to {f1(C(*g3_6h, k=2))}) and "
        f"used {f2(C(*g3_6h, 'fleet'))} more vehicles.", "",
        tab("Paired contrasts on the " + str(len(seeds)) + " development instances (exploratory). Service differences are "
            "in percentage points over all instances; distance differences are percentage changes and vehicle "
            "differences are means, both over instances where both configurations have a plan. Intervals are 95\\% "
            "paired bootstrap intervals over instances.",
            "tab:robust-contrasts", r"@{}>{\raggedright\arraybackslash}p{5.6cm}lll@{}",
            r"Contrast & Service [95\%] & Distance (\%) [95\%] & Vehicles", con_rows),
        f"The screening layer can also wrap the robust generator. Screened robust with relief was admitted by screening "
        f"on {adm_cap} of {len(seeds)} instances and pooled {f1(T('screened_cap')['service'])}\\%, "
        f"{f1(C('screened_cap', 'hgs:hgs_capped_cons'))} points above the HGS capped procedure (interval "
        f"{f1(C('screened_cap', 'hgs:hgs_capped_cons', k=1))} to {f1(C('screened_cap', 'hgs:hgs_capped_cons', k=2))}), "
        f"with {f2(C('screened_cap', 'hgs:hgs_capped_cons', 'fleet'))} more vehicles. Against the most protective "
        f"relieved setting it gave up {f1(-C('screened_cap', 'cap:box_d0.6'))} points and saved "
        f"{f1(-C('screened_cap', 'cap:box_d0.6', 'distance'))}\\% of distance, because it selects the shortest plan "
        f"that passes the screen. Without relief, screening admitted a robust plan on {adm_rob} instances and pooled "
        f"{f1(T('screened')['service'])}\\%.", "",
        "These development results are exploratory, and part A of the third protocol tests them below. The settings "
        "in Table~\\ref{tab:robust} were picked after the grid was run, to show the trade-off: $\\Gamma=3$, a middle "
        "budget, and box uncertainty, the most protective, each at two protection levels; the appendix reports "
        "every setting. "
        "The robust plans minimize distance alone, without the slack, duration and fleet terms of the screened "
        "procedures, so differences in vehicles are part of the comparison.", "",
        r"\begin{figure}[ht]", r" \centering", r" \includegraphics[width=0.93\textwidth]{Fig2.pdf}",
        r" \caption{Pooled validated service-event probability against mean distance relative to the nominal plan of "
        f"the robust search, on the {len(seeds)} development instances. Lines join the relieved robust settings for "
        f"each ${th}$, from $\\Gamma=1$ to box uncertainty. The screened procedures (OR-Tools, HGS), screened robust "
        r"with relief and conservative speed are shown separately, with 95\% bootstrap intervals over instances for "
        r"their service probability. The dashed line marks the 95\% target}",
        r" \label{fig:robust}", r"\end{figure}", "",
    ]
    (ROOT / "paper/robust_results.tex").write_text("\n".join(text))

    grid_rows = []
    for variant, vname in (("rob", "Standard"), ("cap", "Relief")):
        for d in DELTAS:
            for g in GAMMAS:
                x = grid[f"{variant}:{key(g, d)}"]
                gl = "box" if g == "box" else str(g)
                grid_rows.append(f"{vname} & {d:g} & {gl} & {x['all']['plans']} & "
                                 + " & ".join(f1(x[n]['service']) for n in SIZES)
                                 + f" & {f1(x['all']['service'])} & {f1(x['all']['distance'])} & {f2(x['all']['fleet'])}")
    nom = {"all": stats("rob:G0_d0", seeds), **{n: stats("rob:G0_d0", [s for s in seeds if n_of[s] == n]) for n in SIZES}}
    grid_rows.insert(0, f"Nominal & 0 & 0 & {nom['all']['plans']} & " + " & ".join(f1(nom[n]['service']) for n in SIZES)
                     + f" & {f1(nom['all']['service'])} & {f1(nom['all']['distance'])} & {f2(nom['all']['fleet'])}")
    (ROOT / "paper/robust_appendix.tex").write_text(tab(
        "Every robust setting on the " + str(len(seeds)) + " development instances: instances with a plan, mean "
        "validated service-event probability (\\%) by size and pooled, mean distance relative to the nominal plan and "
        "mean vehicles over instances with a plan. A missing plan scores zero.",
        "tab:robust-grid", r"@{}lllrrrrrrr@{}",
        r"Model & $\theta$ & $\Gamma$ & Plans & $n=20$ & $n=50$ & $n=100$ & Pooled & Dist. (\%) & Veh.",
        grid_rows, size="scriptsize"))

    # ---- Fig. 2 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    installed = {f.name for f in font_manager.fontManager.ttflist}
    sans = next((f for f in ("Arial", "Liberation Sans", "Helvetica") if f in installed), "DejaVu Sans")
    plt.rcParams.update({"font.size": 9, "font.family": "sans-serif", "font.sans-serif": [sans],
                         "mathtext.fontset": "custom", "mathtext.rm": sans, "mathtext.it": sans + ":italic",
                         "mathtext.cal": sans, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(6.3, 3.9))
    for d, marker, shade in ((0.2, "o", "0.68"), (0.4, "s", "0.45"), (0.6, "^", "0.15")):
        xs = [grid[f"cap:{key(g, d)}"]["all"]["distance"] for g in GAMMAS]
        ys = [grid[f"cap:{key(g, d)}"]["all"]["service"] for g in GAMMAS]
        ax.plot(xs, ys, color=shade, marker=marker, markersize=5, linewidth=1.5, label=rf"Relief, $\theta={d:g}$")
    pts = [("OR-Tools capped", "ort:capped_procedure", "D"), ("HGS capped", "hgs:hgs_capped_cons", "P"),
           ("Screened robust\nwith relief", "screened_cap", "*"), ("Conservative\nspeed", "ort:conservative", "X")]
    offsets = {"ort:capped_procedure": (6, -10), "hgs:hgs_capped_cons": (6, -12), "screened_cap": (-80, 10),
               "ort:conservative": (6, -4)}
    for label, c, marker in pts:
        x, y = T(c)["distance"], T(c)["service"]
        _, lo, hi = boot([serv(cfg(s, c)) for s in seeds])      # 95% bootstrap interval of pooled service
        ax.errorbar([x], [y], yerr=[[y - lo], [hi - y]], fmt="none", ecolor="black", elinewidth=0.8, capsize=2.5)
        ax.plot([x], [y], linestyle="none", marker=marker, markersize=8 if marker != "*" else 11,
                color="black", markerfacecolor="white" if marker in "DX" else "black")
        ax.annotate(label, (x, y), textcoords="offset points", xytext=offsets[c], fontsize=8)
    ax.axhline(95, color="#17375e", linewidth=0.8, linestyle="--")
    ax.set(xlabel="Distance relative to the nominal plan (%)", ylabel="Pooled service probability (%)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    for out in ("paper/Fig2.pdf", "paper/Fig2.eps"):
        fig.savefig(ROOT / out, bbox_inches="tight")
    plt.close(fig)
    (ROOT / "results/robust_summary.json").write_text(json.dumps(
        {"macros": macros, "table": {c: table[c] for _, c in rows_main},
         "grid": grid, "contrasts": {f"{a2} minus {b2}": con[(a2, b2)] for _, a2, b2 in contrasts}},
        indent=1, default=str))
    print(json.dumps(macros, indent=1))


if __name__ == "__main__":
    main()
