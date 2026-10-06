"""Generate version-6 manuscript tables, figure, and summary JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BOOTSTRAPS = 20_000
CONFIGS = ("distance", "peak_aware", "slack_aware", "fleet_matched", "procedure")
LABELS = {
    "distance": "Nominal distance",
    "peak_aware": "Peak-aware distance",
    "slack_aware": "Slack-aware",
    "fleet_matched": "Fleet-matched distance",
    "procedure": "Screened procedure",
}


def read_many(paths):
    records, metadata = [], []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(payload["records"])
        metadata.append({key: value for key, value in payload.items() if key != "records"})
    return records, metadata


def bootstrap(values, rng):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return None
    mean = float(values.mean())
    if len(values) == 1:
        return mean, mean, mean
    indices = rng.integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    draws = values[indices].mean(axis=1)
    low, high = np.percentile(draws, [2.5, 97.5])
    return mean, float(low), float(high)


def pct(interval, digits=1):
    if interval is None:
        return "--"
    mean, low, high = interval
    return f"{100*mean:.{digits}f} [{100*low:.{digits}f}, {100*high:.{digits}f}]"


def num(interval, digits=2):
    if interval is None:
        return "--"
    mean, low, high = interval
    return f"{mean:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def rel_change(new, old):
    return (float(new) - float(old)) / float(old)


def stochastic(row, config, field):
    return row["configurations"][config]["stochastic"][field]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", type=Path, nargs="+", required=True)
    parser.add_argument("--extended", type=Path, nargs="+", required=True)
    parser.add_argument("--previous-main", type=Path, nargs="+", required=True)
    parser.add_argument("--benchmark", type=Path, nargs="+", required=True)
    parser.add_argument("--paper-dir", type=Path, default=Path("paper"))
    parser.add_argument("--summary", type=Path, default=Path("results/summary_v6.json"))
    args = parser.parse_args()

    main_records, main_meta = read_many(args.main)
    extended_records, extended_meta = read_many(args.extended)
    previous_records, previous_meta = read_many(args.previous_main)
    benchmark_records, benchmark_meta = read_many(args.benchmark)
    main_by_key = {(int(r["customers"]), int(r["instance_seed"])): r for r in main_records}
    ext_by_key = {(int(r["customers"]), int(r["instance_seed"])): r for r in extended_records}
    prev_by_key = {(int(r["customers"]), int(r["instance_seed"])): r for r in previous_records}
    if set(main_by_key) != set(ext_by_key) or set(main_by_key) != set(prev_by_key):
        raise ValueError("v5, v6, and extended record keys differ")

    rng = np.random.default_rng(20260930)
    sizes = sorted({key[0] for key in main_by_key})
    service_rows, screening_rows, ontime_rows, late_rows = [], [], [], []
    cost_rows, decomposition_rows, benchmark_rows = [], [], []
    plot = {key: [] for key in ("distance", "peak_aware", "slack_aware", "procedure")}
    plot_low = {key: [] for key in plot}
    plot_high = {key: [] for key in plot}
    selected_labels = []
    all_thresholds = {
        config: {k: [] for k in ("0.90", "0.95", "0.98", "1.00")}
        for config in CONFIGS
    }
    all_sensitivity = {config: {} for config in CONFIGS}
    summary = {
        "schema": "routeops-v6-summary-1",
        "bootstrap_resamples": BOOTSTRAPS,
        "main_metadata": main_meta,
        "extended_metadata": extended_meta,
        "previous_metadata": previous_meta,
        "benchmark_metadata": benchmark_meta,
        "sizes": {},
    }

    for n in sizes:
        keys = sorted(key for key in main_by_key if key[0] == n)
        mains = [main_by_key[key] for key in keys]
        exts = [ext_by_key[key] for key in keys]
        prevs = [prev_by_key[key] for key in keys]
        service = {
            config: bootstrap([
                row["configurations"][config]["stochastic"]
                ["service_probability_by_kappa"]["0.95"] for row in exts
                if row["configurations"][config] is not None
            ], rng)
            for config in CONFIGS
        }
        peak_feasible = sum(
            row["configurations"]["peak_aware"] is not None for row in exts
        )
        service_rows.append(
            f"{n} & {len(keys)} & {peak_feasible}/{len(keys)} & {pct(service['distance'])} & "
            f"{pct(service['peak_aware'])} & {pct(service['slack_aware'])} & "
            f"{pct(service['fleet_matched'])} & {pct(service['procedure'])} \\\\"
        )

        selected = [r for r in mains if r["screened"]["selected_plan"] is not None]
        retained = [
            r for r in selected
            if r["screened"]["validation"]["service_level_lcb"] >= 0.95
        ]
        previous_selected = sum(
            r["screened"]["selected_plan"] is not None for r in prevs
        )
        failures = [r for r in mains if r["screened"]["selected_plan"] is None]
        best_lcb = bootstrap([
            r["screened"]["diagnostic"]["best_service_lcb"] for r in failures
            if r["screened"]["diagnostic"]["best_service_lcb"] is not None
        ], rng)
        ceiling = sum(
            r["screened"]["diagnostic"]["failure_mode"]
            == "grid ceiling reached without passing" for r in failures
        )
        infeasible = sum(
            r["screened"]["diagnostic"]["failure_mode"]
            == "contracted solves infeasible before grid ceiling" for r in failures
        )
        screening_rows.append(
            f"{n} & {previous_selected}/{len(keys)} & {len(selected)}/{len(keys)} & "
            f"{len(retained)}/{len(selected)} & {pct(best_lcb)} & {ceiling} & {infeasible} \\\\"
        )

        ontime = {
            config: bootstrap([
                stochastic(r, config, "mean_on_time_fraction") for r in exts
                if r["configurations"][config] is not None
            ], rng) for config in CONFIGS
        }
        late = {
            config: bootstrap([
                stochastic(r, config, "expected_late_customers") for r in exts
                if r["configurations"][config] is not None
            ], rng) for config in CONFIGS
        }
        ontime_rows.append(
            f"{n} & {pct(ontime['distance'])} & {pct(ontime['peak_aware'])} & "
            f"{pct(ontime['slack_aware'])} & {pct(ontime['fleet_matched'])} & "
            f"{pct(ontime['procedure'])} \\\\"
        )
        late_rows.append(
            f"{n} & {num(late['distance'])} & {num(late['peak_aware'])} & "
            f"{num(late['slack_aware'])} & {num(late['fleet_matched'])} & "
            f"{num(late['procedure'])} \\\\"
        )

        changes = {}
        for config in ("peak_aware", "slack_aware", "fleet_matched", "procedure"):
            changes[config] = {
                "distance": bootstrap([
                    rel_change(
                        r["configurations"][config]["plan_metrics"]["distance"],
                        r["configurations"]["distance"]["plan_metrics"]["distance"],
                    ) for r in exts if r["configurations"][config] is not None
                ], rng),
                "duration": bootstrap([
                    rel_change(
                        r["configurations"][config]["plan_metrics"]["driver_duration"],
                        r["configurations"]["distance"]["plan_metrics"]["driver_duration"],
                    ) for r in exts if r["configurations"][config] is not None
                ], rng),
                "fleet": bootstrap([
                    r["configurations"][config]["plan_metrics"]["fleet"]
                    - r["configurations"]["distance"]["plan_metrics"]["fleet"]
                    for r in exts if r["configurations"][config] is not None
                ], rng),
            }
            cost_rows.append(
                f"{n} & {LABELS[config]} & {pct(changes[config]['distance'])} & "
                f"{pct(changes[config]['duration'])} & {num(changes[config]['fleet'])} \\\\"
            )

        decomposition = {}
        for config in ("distance", "peak_aware", "slack_aware"):
            decomposition[config] = {
                "sigma0": bootstrap([
                    r["configurations"][config]["time_dependent_no_noise"]
                    ["mean_on_time_fraction"] for r in exts
                    if r["configurations"][config] is not None
                ], rng),
                "sigma20": ontime[config],
            }
        decomposition_rows.append(
            f"{n} & {pct(decomposition['distance']['sigma0'])} & "
            f"{pct(decomposition['distance']['sigma20'])} & "
            f"{pct(decomposition['peak_aware']['sigma0'])} & "
            f"{pct(decomposition['peak_aware']['sigma20'])} & "
            f"{pct(decomposition['slack_aware']['sigma0'])} & "
            f"{pct(decomposition['slack_aware']['sigma20'])} \\\\"
        )

        for row in exts:
            for config in CONFIGS:
                if row["configurations"][config] is None:
                    continue
                stochastic_values = row["configurations"][config]["stochastic"]
                for kappa, value in stochastic_values["service_probability_by_kappa"].items():
                    all_thresholds[config][kappa].append(value)
                sensitivity = row["configurations"][config]["parameter_sensitivity"]
                for setting, values in sensitivity.items():
                    all_sensitivity[config].setdefault(setting, []).append(
                        values["service_probability_by_kappa"]["0.95"]
                    )

        for config in plot:
            interval = service[config]
            plot[config].append(interval[0])
            plot_low[config].append(interval[0] - interval[1])
            plot_high[config].append(interval[2] - interval[0])
        selected_labels.append(f"{len(selected)}/{len(keys)}")
        summary["sizes"][str(n)] = {
            "instances": len(keys),
            "peak_aware_feasible": peak_feasible,
            "service": service,
            "screen_selected_one_second": previous_selected,
            "screen_selected_five_seconds": len(selected),
            "selected_validation_pass": len(retained),
            "failure_best_lcb": best_lcb,
            "failure_modes": {
                "ceiling": ceiling,
                "infeasible_before_ceiling": infeasible,
            },
            "customer_on_time": ontime,
            "expected_late": late,
            "operational_change_vs_nominal_distance": changes,
            "decomposition": decomposition,
            "paired_peak_minus_nominal": bootstrap([
                r["configurations"]["peak_aware"]["stochastic"]
                ["service_probability_by_kappa"]["0.95"]
                - r["configurations"]["distance"]["stochastic"]
                ["service_probability_by_kappa"]["0.95"]
                for r in exts if r["configurations"]["peak_aware"] is not None
            ], rng),
            "paired_slack_minus_peak": bootstrap([
                r["configurations"]["slack_aware"]["stochastic"]
                ["service_probability_by_kappa"]["0.95"]
                - r["configurations"]["peak_aware"]["stochastic"]
                ["service_probability_by_kappa"]["0.95"]
                for r in exts if r["configurations"]["peak_aware"] is not None
            ], rng),
        }

    allowed = {
        "0.90": "2/5/10/20", "0.95": "1/2/5/10",
        "0.98": "0/1/2/4", "1.00": "0/0/0/0",
    }
    threshold_rows, threshold_summary = [], {}
    for kappa in ("0.90", "0.95", "0.98", "1.00"):
        vals = {
            config: bootstrap(all_thresholds[config][kappa], rng)
            for config in CONFIGS
        }
        threshold_rows.append(
            f"{kappa} & {allowed[kappa]} & {pct(vals['distance'])} & "
            f"{pct(vals['peak_aware'])} & {pct(vals['slack_aware'])} & "
            f"{pct(vals['fleet_matched'])} & {pct(vals['procedure'])} \\\\"
        )
        threshold_summary[kappa] = vals
    summary["kappa_sensitivity"] = threshold_summary

    sensitivity_rows, sensitivity_summary = [], {}
    def setting_key(setting):
        sigma_text, rho_text = setting.split(",")
        return float(sigma_text.split("=")[1]), float(rho_text.split("=")[1])
    for setting in sorted(all_sensitivity["distance"], key=setting_key):
        sigma_text, rho_text = setting.split(",")
        sigma, rho = sigma_text.split("=")[1], rho_text.split("=")[1]
        vals = {
            config: bootstrap(all_sensitivity[config][setting], rng)
            for config in CONFIGS
        }
        sensitivity_rows.append(
            f"{sigma} & {rho} & {pct(vals['distance'])} & {pct(vals['peak_aware'])} & "
            f"{pct(vals['slack_aware'])} & {pct(vals['fleet_matched'])} & "
            f"{pct(vals['procedure'])} \\\\"
        )
        sensitivity_summary[setting] = vals
    summary["sigma_rho_sensitivity"] = sensitivity_summary

    benchmark_valid, benchmark_failures = {}, {}
    for n in sizes:
        cells, valid, failures = [], [], []
        for budget in (1.0, 5.0):
            rows = [
                r for r in benchmark_records
                if int(r["customers"]) == n and float(r["budget_seconds"]) == budget
            ]
            values = [
                r["ortools_excess_distance_percent"] / 100 for r in rows
                if r["ortools_excess_distance_percent"] is not None
            ]
            cells.append(bootstrap(values, rng))
            valid.append(len(values)); failures.append(len(rows) - len(values))
        benchmark_rows.append(
            f"{n} & {valid[0]}/{valid[1]} & {pct(cells[0])} & {pct(cells[1])} \\\\"
        )
        benchmark_valid[str(n)] = valid; benchmark_failures[str(n)] = failures
        summary["sizes"][str(n)]["benchmark_ortools_excess"] = {
            "one_second": cells[0], "five_seconds": cells[1],
        }
    summary["benchmark_valid_pairs"] = benchmark_valid
    summary["benchmark_failures"] = benchmark_failures

    selected_1 = sum(v["screen_selected_one_second"] for v in summary["sizes"].values())
    selected_5 = sum(v["screen_selected_five_seconds"] for v in summary["sizes"].values())
    retained = sum(v["selected_validation_pass"] for v in summary["sizes"].values())
    total = sum(v["instances"] for v in summary["sizes"].values())
    peak_delta = [summary["sizes"][str(n)]["paired_peak_minus_nominal"][0] for n in sizes]
    slack_over_peak = [summary["sizes"][str(n)]["paired_slack_minus_peak"][0] for n in sizes]
    slack_fleet = [
        summary["sizes"][str(n)]["operational_change_vs_nominal_distance"]
        ["slack_aware"]["fleet"][0] for n in sizes
    ]
    fleet_matched_gap = [
        summary["sizes"][str(n)]["service"]["fleet_matched"][0]
        - summary["sizes"][str(n)]["service"]["distance"][0]
        for n in sizes
    ]
    procedure_distance = [
        summary["sizes"][str(n)]["operational_change_vs_nominal_distance"]
        ["procedure"]["distance"][0] for n in sizes
    ]
    procedure_fleet = [
        summary["sizes"][str(n)]["operational_change_vs_nominal_distance"]
        ["procedure"]["fleet"][0] for n in sizes
    ]
    sensitivity_procedure = [
        interval["procedure"][0] for interval in sensitivity_summary.values()
    ]

    latex = f"""\\subsection{{Mechanism-aware reliability comparison}}

Table~\\ref{{tab:service-results}} compares the principal mechanisms. The
peak-aware distance baseline plans every arc at the
07:00--09:00 speed of 33.3 km/h, while evaluation still uses the full FIFO
clock profile and identical held-out scenarios. The fleet-matched distance
baseline is initialized from, and constrained to use exactly the same number
of vehicles as, the slack-aware plan. Entries are means with 95\\% paired
bootstrap intervals across instances.

\\begin{{table}}[ht]
\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{3.2pt}}
\\caption{{Validated $\\kappa=0.95$ service-event probability (\\%). Nominal uses a fixed 40 km/h planning matrix; peak-aware uses 33.3 km/h and its mean is conditional on a feasible plan being returned, with the count shown; fleet-matched uses the slack-aware fleet count; procedure includes its prespecified fallback.}}
\\label{{tab:service-results}}
\\begin{{tabular}}{{rrrrrrrr}}\\toprule
$n$ & $k$ & Peak feasible & Nominal & Peak-aware & Slack-aware & Fleet-matched & Procedure\\\\\\midrule
{chr(10).join(service_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

Peak awareness alone changes mean service probability by
{100*min(peak_delta):.1f}--{100*max(peak_delta):.1f} percentage points relative
to the nominal distance baseline. After that predictable mismatch is removed,
slack-aware minus peak-aware ranges from {100*min(slack_over_peak):.1f} to
{100*max(slack_over_peak):.1f} points. Thus the nominal-distance contrast mainly
reflects predictable peak mismatch: slack awareness improves on the
misspecified nominal baseline but does not outperform conservative peak
planning. The conservative comparator is not universally feasible, so this is
mechanism evidence rather than a deployable replacement policy.

\\subsection{{Screening success and failure diagnosis}}

\\begin{{table}}[ht]
\\centering\\scriptsize
\\caption{{Screening diagnosis. Selected is the number whose screening Wilson lower bound reaches 0.95. Retained is the number of five-second selections whose held-out validation lower bound also reaches 0.95. Best LCB is averaged only over five-second failures. Ceiling and infeasible classify those failures.}}
\\label{{tab:screening-diagnosis}}
\\begin{{tabular}}{{rrrrrrr}}\\toprule
$n$ & Selected (1s) & Selected (5s) & Retained & Failure best LCB & Ceiling & Infeasible\\\\\\midrule
{chr(10).join(screening_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

Raising the candidate budget changes screening success from {selected_1} to
{selected_5} of {total} instances. Of the five-second selections, {retained}
retain the target on the untouched bank. Table~\\ref{{tab:screening-diagnosis}}
also distinguishes a feasible $\\beta=60$ ceiling from loss of nominal
feasibility under contraction; therefore an unselected instance is not treated
as a single undifferentiated method failure.

\\subsection{{Customer outcomes and operational resources}}

Slack-aware fleet use changes by {min(slack_fleet):.2f} to
{max(slack_fleet):.2f} vehicles across sizes, so its reliability gain is not
explained by adding vans. Conversely, forcing distance minimization to the same
fleet count changes service probability by only
{100*min(fleet_matched_gap):.1f} to {100*max(fleet_matched_gap):.1f} points
relative to nominal distance. Route scheduling and sequence, rather than fleet
count alone, are therefore consequential. The complete procedure costs
{100*min(procedure_distance):.1f}--{100*max(procedure_distance):.1f}\\% distance
and {min(procedure_fleet):.2f}--{max(procedure_fleet):.2f} vehicles on average.

\\begin{{table}}[ht]\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{3.4pt}}
\\caption{{Validated mean on-time customer fraction (\\%).}}
\\label{{tab:ontime-results}}
\\begin{{tabular}}{{rrrrrr}}\\toprule
$n$ & Nominal & Peak-aware & Slack-aware & Fleet-matched & Procedure\\\\\\midrule
{chr(10).join(ontime_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

\\begin{{table}}[ht]\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{3.4pt}}
\\caption{{Expected number of late customers; mean [95\\% bootstrap interval].}}
\\label{{tab:late-results}}
\\begin{{tabular}}{{rrrrrr}}\\toprule
$n$ & Nominal & Peak-aware & Slack-aware & Fleet-matched & Procedure\\\\\\midrule
{chr(10).join(late_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

\\begin{{table}}[ht]\\centering\\scriptsize
\\caption{{Paired operational change relative to nominal distance-only; distance and duration are percentages, vehicles are absolute differences.}}
\\label{{tab:operational-cost}}
\\begin{{tabular}}{{rlrrr}}\\toprule
$n$ & Configuration & Distance & Driver duration & Vehicles\\\\\\midrule
{chr(10).join(cost_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

\\subsection{{Predictable congestion, randomness, and parameter sensitivity}}

The clock-origin convention is explicit: relative time zero is 06:00. Without
the 360-minute offset, passing relative time directly to the clock profile
would instead evaluate a 00:00--10:00 shift. Table~\\ref{{tab:decomposition}}
shows the remaining effect of adding
random disturbances after retaining predictable time dependence.

\\begin{{table}}[ht]\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{3.1pt}}
\\caption{{Mean on-time customer fraction (\\%) with time dependence retained; peak-aware values are conditional on feasibility counts in Table~\\ref{{tab:service-results}}.}}
\\label{{tab:decomposition}}
\\begin{{tabular}}{{rrrrrrr}}\\toprule
& \\multicolumn{{2}}{{c}}{{Nominal}} & \\multicolumn{{2}}{{c}}{{Peak-aware}} & \\multicolumn{{2}}{{c}}{{Slack-aware}}\\\\
$n$ & $\\sigma=0$ & $\\sigma=.20$ & $\\sigma=0$ & $\\sigma=.20$ & $\\sigma=0$ & $\\sigma=.20$\\\\\\midrule
{chr(10).join(decomposition_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

\\begin{{table}}[ht]\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{2.7pt}}
\\caption{{Service-event probability pooled over 53 instances by $\\kappa$; allowed-late counts correspond to $n=20/50/100/200$, and peak-aware values use its 46 feasible instances.}}
\\label{{tab:kappa}}
\\begin{{tabular}}{{rrrrrrr}}\\toprule
$\\kappa$ & Allowed late & Nominal & Peak-aware & Slack-aware & Fleet-matched & Procedure\\\\\\midrule
{chr(10).join(threshold_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

The exploratory $\\sigma$--$\\rho$ sweep in Table~\\ref{{tab:sigma-rho}} uses
1,000 common scenarios per cell and is separate from the 5,000-scenario primary
validation bank. Procedure-level service probability ranges from
{100*min(sensitivity_procedure):.1f}\\% to
{100*max(sensitivity_procedure):.1f}\\% across the grid, confirming that the
quantitative claim is conditional on both disturbance scale and dependence.

\\begin{{table}}[ht]\\centering\\scriptsize\\setlength{{\\tabcolsep}}{{2.7pt}}
\\caption{{Pooled $\\kappa=0.95$ service-event probability (\\%) over disturbance parameters; peak-aware values use its 46 feasible instances.}}
\\label{{tab:sigma-rho}}
\\begin{{tabular}}{{rrrrrrr}}\\toprule
$\\sigma$ & $\\rho$ & Nominal & Peak-aware & Slack-aware & Fleet-matched & Procedure\\\\\\midrule
{chr(10).join(sensitivity_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}

\\subsection{{Deterministic solver-quality check}}

The retained candidate budget is now five seconds. Table~\\ref{{tab:benchmark}}
keeps both equal-budget comparisons so the earlier one-second starvation is
visible rather than discarded. Positive values mean OR-Tools returned the
longer route; missing pairs are excluded from means and disclosed by the valid
count.

\\begin{{table}}[ht]\\centering\\small
\\caption{{OR-Tools excess distance over PyVRP/HGS under equal budgets (\\%).}}
\\label{{tab:benchmark}}
\\begin{{tabular}}{{rrrr}}\\toprule
$n$ & Valid pairs (1s/5s) & One second & Five seconds\\\\\\midrule
{chr(10).join(benchmark_rows)}
\\bottomrule\\end{{tabular}}\\end{{table}}
"""

    args.paper_dir.mkdir(parents=True, exist_ok=True)
    (args.paper_dir / "results_summary_v6.tex").write_text(latex, encoding="utf-8")

    x = np.arange(len(sizes)); width = 0.19
    fig, ax = plt.subplots(figsize=(6.1, 3.75))
    styles = (
        ("distance", "Nominal distance", "#202020"),
        ("peak_aware", "Peak-aware distance", "#5b5b5b"),
        ("slack_aware", "Slack-aware", "#929292"),
        ("procedure", "Screened procedure", "#cccccc"),
    )
    for offset, (key, label, colour) in enumerate(styles):
        positions = x + (offset - 1.5) * width
        values = np.array(plot[key]) * 100
        bars = ax.bar(
            positions, values, width,
            yerr=np.array([plot_low[key], plot_high[key]]) * 100,
            label=label, color=colour, edgecolor="black", linewidth=0.6, capsize=2.5,
        )
        if key == "procedure":
            for bar, text in zip(bars, selected_labels):
                ax.text(
                    bar.get_x() + bar.get_width()/2, bar.get_height()+3.2, text,
                    ha="center", va="bottom", fontsize=7,
                )
    ax.axhline(95, color="#1f4e79", linewidth=1.0, linestyle="--")
    ax.set_xticks(x, [str(n) for n in sizes]); ax.set_xlabel("Customers")
    ax.set_ylabel("Validated service-event probability (%)"); ax.set_ylim(0, 112)
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.24))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(args.paper_dir / "reliability_v6.pdf", bbox_inches="tight")

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
