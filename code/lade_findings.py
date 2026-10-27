"""Evidence from real pickup operations (LaDe): the numbers reported in the manuscript (exploratory).

  1. Operational time stamps are not delay data. For busy courier-days (>= BUSY pickups) the
     courier's real gaps between pickups, replayed in the real order with the real windows,
     reproduce the observed lateness; the same gaps in random order (SHUFFLES permutations)
     make most routes late. Every city of the trajectory-period tables (21 March to 20 April
     2022) and the main LaDe-P files for Jilin and Shanghai (May to October 2022).
  2. A delay model learned from those gaps (code/lade.py, busy courier-days of May to August)
     predicts far more lateness on the real busy routes of September and October than happened.
  3. Travel and handling measured from GPS on direct trips (code/lade_traj.py): pace (seconds of
     movement per metre) and still time, in the first 21 days against the last 10, per city.
  4. Real teams of three couriers and their real promised windows (code/lade_field.py): share
     of teams of the last 10 days with no feasible plan for three vehicles at nominal times.
  5. Days of history a model-free certificate needs at tau = 0.95, alpha = 0.05.

Usage (from the package root):
  PYTHONPATH=code python code/lade_findings.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import lade
import lade_field as lf
import lade_traj as lt
from certify import cp_lower

ROOT = Path(__file__).resolve().parents[1]
BUSY = 30
SHUFFLES = 200
TEAMS = 150
SEED = 20261027


def replay_shuffle(frames):
    """frames: iterable of (pickup time, earliest, window end) arrays per courier-day, in real order."""
    rng = np.random.default_rng(SEED)
    rep, obs, shu = [], [], []
    for t, lo, hi in frames:
        gaps = np.diff(t)

        def run(gs):
            now, late = t[0], t[0] > hi[0]
            for k, g in enumerate(gs, 1):
                now = max(now + g, lo[k])
                late |= now > hi[k] + 1e-9
            return late
        rep.append(run(gaps))
        obs.append(bool((t > hi).any()))
        shu.append(np.mean([run(rng.permutation(gaps)) for _ in range(SHUFFLES)]))
    return {"courier_days": len(rep), "replay_late": float(np.mean(rep)), "observed_late": float(np.mean(obs)),
            "shuffled_late": float(np.mean(shu))}


def frames_main(city):
    d = lade.load(city)
    for _, g in d.groupby(["courier_id", "ds"]):
        if len(g) >= BUSY:
            g = g.sort_values(["pickup_time_min", "order_id"])
            yield g.pickup_time_min.values, g.accept_time_min.values, g.time_window_end_min.values


def frames_traj(city):
    p = lt.pickups(city)
    p = p[p.got_time_s.notna() & p.expect_got_time_s.notna()]
    for _, g in p.groupby(["delivery_user_id", "ds"]):
        if len(g) >= BUSY:
            g = g.sort_values(["got_time_s", "order_id"])
            yield g.got_time_s.values, g.accept_time_s.fillna(0).values, g.expect_got_time_s.values


def logs_model_calibration():
    d = lade.load("jl")
    L = lade.legs(d)
    L = L.join(d.groupby(["courier_id", "ds"]).size().rename("orders"), on=["courier_id", "ds"])
    hist = lade.History.fit(L[L.month.isin(lade.TRAIN_MONTHS) & (L.orders >= BUSY)])
    pred, obs = [], []
    for (cid, ds), g in d[d.month.isin(lade.TEST_MONTHS)].groupby(["courier_id", "ds"]):
        if len(g) < BUSY:
            continue
        g = g.sort_values(["pickup_time_min", "order_id"])
        blocks = []
        for o in g.itertuples():
            if blocks and blocks[-1]["aoi"] == o.aoi_id:
                b = blocks[-1]
                b["n"] += 1
                b["lo"] = max(b["lo"], o.accept_time_min)
                b["hi"] = min(b["hi"], o.time_window_end_min)
            else:
                blocks.append({"aoi": o.aoi_id, "lat": o.lat, "lng": o.lng, "n": 1,
                               "lo": o.accept_time_min, "hi": o.time_window_end_min})
        lat = np.array([b["lat"] for b in blocks]); lng = np.array([b["lng"] for b in blocks])
        km = lade.hav(lat[:, None], lng[:, None], lat[None, :], lng[None, :])
        dr = lade.DayDraws(hist, 1000, int(cid) * 1000 + int(ds), 1)
        late = lade.simulate_route(list(range(len(blocks))), km, [b["n"] - 1 for b in blocks],
                                   np.array([b["lo"] for b in blocks]), np.array([b["hi"] for b in blocks]),
                                   float(g.pickup_time_min.iloc[0]), dr, 0)
        pred.append(float(late.mean()))
        obs.append(bool((g.pickup_time_min > g.time_window_end_min).any()))
    return {"courier_days": len(pred), "predicted_late": float(np.mean(pred)), "observed_late": float(np.mean(obs))}


def gps_stability(city):
    L = lf.city_legs(city)
    hist, fut = lf.periods()
    X = L[L.direct & ~L.same_aoi & (L.straight > 100)].copy()
    X["pace"] = X.moving / X.straight
    out = {"legs": int(len(L)), "direct_share": float(L.direct.mean()), "direct_legs": int(len(X)),
           "speed_ms_median": float(np.median(X.straight / X.moving.clip(lower=20)))}
    for nm, days in (("history", hist), ("future", fut)):
        Y = X[X.ds.isin(days)]
        out[nm] = {"legs": int(len(Y)), "pace_median": float(Y.pace.median()), "pace_mean": float(Y.pace.mean()),
                   "still_median": float(Y.still.median()), "still_mean": float(Y.still.mean()),
                   "still_p90": float(Y.still.quantile(0.9))}
    # day-to-day spread of the daily median pace
    dm = X.groupby("ds").pace.median()
    out["daily_pace_median_q05_q95"] = [float(dm.quantile(0.05)), float(dm.quantile(0.95))]
    return out


def team_feasibility(city):
    _, keys = lf.instances(city)
    H = lf.Pools(city, lf.periods()[0])
    feas, early = [], []
    for k in range(min(TEAMS, len(keys))):
        inst = lf.build(city, *keys[k])
        plan = lf.solve(inst, lf.nominal_times(inst, H), inst["hi"])
        feas.append(plan is not None)
    p = lt.pickups(city)
    p = p[p.ds.isin(lf.periods()[1]) & p.got_time_s.notna()]
    return {"teams": len(feas), "feasible": int(sum(feas)), "infeasible_share": float(1 - np.mean(feas)),
            "early_pickup_share": float((p.got_time_s < p.book_start_time_s).mean()),
            "late_pickup_share": float((p.got_time_s > p.expect_got_time_s).mean())}


def days_needed():
    out = {}
    for f in range(4):
        out[f"failures_{f}"] = next(n for n in range(1, 5000) if cp_lower(n - f, n) >= 0.95)
    out["bound_21_of_21"] = float(cp_lower(21, 21))
    return out


def main():
    res = {"busy": BUSY, "shuffles": SHUFFLES}
    res["replay_shuffle"] = {}
    for city in ("jl", "sh"):
        res["replay_shuffle"][f"{city}_main"] = replay_shuffle(frames_main(city))
        print(city, res["replay_shuffle"][f"{city}_main"], flush=True)
    for city in lt.CITY:
        res["replay_shuffle"][f"{city}_traj"] = replay_shuffle(frames_traj(city))
        print(city, res["replay_shuffle"][f"{city}_traj"], flush=True)
    res["logs_model"] = logs_model_calibration()
    print(res["logs_model"], flush=True)
    res["gps"] = {}
    for city in lt.CITY:
        res["gps"][city] = gps_stability(city)
        print(city, json.dumps(res["gps"][city]), flush=True)
    res["teams"] = {}
    for city in ("yt", "hz"):
        res["teams"][city] = team_feasibility(city)
        print(city, res["teams"][city], flush=True)
    res["days_needed"] = days_needed()
    (ROOT / "results" / "lade_findings.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["days_needed"]))


if __name__ == "__main__":
    main()
