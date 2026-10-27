"""Field test on real pickup instances with travel times measured from GPS (exploratory development).

Instances (LaDe trajectory period, 21 March to 20 April 2022): a team of TEAM real couriers of
one station on one day of the future period, and the orders they picked up.
  customers   the team's pickup orders, grouped by AOI and promised window; the
              location is the mean order location, mapped into the trajectories' metric frame
              (affine map fitted per city on pickup scans matched to the courier's GPS point)
  window      the real promised two-hour window, planned as a hard window (orders are taken as
              known in the morning, as in the static problem; the data's early pickups and
              acceptance times are not used)
  fleet       TEAM vehicles
  depot       the centre of the team's customers

Travel and handling (code/lade_traj.py): on direct GPS trips between consecutive pickups,
  pace   seconds of movement per metre of straight-line distance,
  still  seconds not moving (handling and waiting at the stop).
A leg of straight distance d takes d * pace + still, where (pace, still) is one real direct
trip; a further order at the same stop takes one real time between two pickups in one AOI.
Nominal (planning) times use the medians.

A simulated day draws one real day of the chosen period and draws every leg of the plan from
that day's direct trips, so a slow day slows every route. Three periods are used:
  history   the first HISTORY_DAYS days: screening (1000 draws) and certification (5000
            draws, independent of the screening draws)
  future    the remaining days: the test (5000 draws), unknown to everything that planned
            or certified

Configurations (HGS through PyVRP, times in seconds):
  nominal         least travel at nominal times, no buffer
  padding20       least travel at nominal times x 1.2
  capped_screen   capped buffers 0..60 min, least travel at nominal times, screened on history
                  days with the Wilson rule, least-travel passing candidate, fallback padding20
  fixed_order     the same candidates certified in fixed order (Proposition 4), cheapest certified

Usage (from the package root), development city only:
  PYTHONPATH=code python code/lade_field.py --city yt --instances 10 --workers 2
  PYTHONPATH=code python code/lade_field.py --city yt --summarise
"""
from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pyvrp import Model
from pyvrp.stop import MaxIterations

import lade_traj as lt
from certify import TARGET, cp_lower, cp_upper

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "lade_field"
HISTORY_DAYS = 21                    # 21 March to 10 April
DAY0 = 7 * 3600                      # time 0 = 07:00
SHIFT = 14 * 3600                    # until 21:00
BETAS = list(range(0, 61, 5))
SCREEN_N, CERT_N, TEST_N = 1000, 5000, 5000
ITER = 5000
ALPHA_SCREEN_Z = 1.6448536269514722  # one-sided 95% Wilson bound


def all_days():
    return sorted(pd.read_parquet(lt.D / "traj" / "pickup_five_cities.parquet", columns=["ds"]).ds.unique())


def periods():
    d = all_days()
    return d[:HISTORY_DAYS], d[HISTORY_DAYS:]


@lru_cache(maxsize=4)
def city_legs(city):
    p = ROOT / "results" / f"lade_traj_legs_{city}.parquet"
    if not p.exists():
        lt.legs(city).to_parquet(p)
    return pd.read_parquet(p)


@lru_cache(maxsize=4)
def frame_map(city):
    """Affine map from the order tables' coordinates to the trajectories' metres."""
    p = lt.pickups(city)
    p = p[p.courier.notna() & p.got_gps_time.notna()].copy()
    ts = pd.to_datetime("2022-" + p.got_gps_time, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    p["ts"] = (ts - pd.Timestamp("2022-03-01")).dt.total_seconds()
    c, t, x, y, _ = lt.load_tracks()
    key = c.astype(np.int64) * 10 ** 8 + t
    k = p.courier.astype(np.int64).values * 10 ** 8 + p.ts.astype(np.int64).values
    i = np.clip(np.searchsorted(key, k), 0, len(key) - 1)
    ok = np.abs(key[i] - k) <= 20
    A = np.c_[p.got_gps_lng.values[ok], p.got_gps_lat.values[ok], np.ones(ok.sum())]
    cx, *_ = np.linalg.lstsq(A, np.asarray(x)[i[ok]], rcond=None)
    cy, *_ = np.linalg.lstsq(A, np.asarray(y)[i[ok]], rcond=None)
    resid = np.hypot(A @ cx - np.asarray(x)[i[ok]], A @ cy - np.asarray(y)[i[ok]])
    return cx, cy, float(np.median(resid))


class Pools:
    """Real direct trips by day, for one period."""

    def __init__(self, city, days):
        L = city_legs(city)
        L = L[L.ds.isin(days)]
        X = L[L.direct & ~L.same_aoi & (L.straight > 100)]
        S = L[L.same_aoi & (L.path < 150)]
        self.days = np.array(sorted(X.ds.unique()))
        self.pace = {d: g.eval("moving / straight").values for d, g in X.groupby("ds")}
        self.still = {d: g.still.values for d, g in X.groupby("ds")}
        self.extra = S.gap.values
        self.nom_pace = float(np.median(X.moving / X.straight))
        self.nom_still = float(np.median(X.still))
        self.nom_extra = float(np.median(S.gap)) if len(S) else 360.0

    def draws(self, n, legs_per_day, seed):
        """For n simulated days: arrays (n, legs) of pace and still, and extra-order times."""
        rng = np.random.default_rng(seed)
        day = rng.choice(self.days, size=n)
        pace = np.empty((n, legs_per_day)); still = np.empty((n, legs_per_day))
        for d in np.unique(day):
            idx = np.flatnonzero(day == d)
            j = rng.integers(0, len(self.pace[d]), size=(len(idx), legs_per_day))
            pace[idx], still[idx] = self.pace[d][j], self.still[d][j]
        extra = rng.choice(self.extra, size=(n, legs_per_day))
        return pace, still, extra


TEAM = 3                             # couriers per instance
MIN_PICKUPS = 5                      # a courier enters a team with at least this many pickups that day


def instances(city):
    """Teams of TEAM real couriers of one station on one future day, drawn with a fixed seed."""
    p = lt.pickups(city)
    _, fut = periods()
    cx, cy, _ = frame_map(city)
    p["X"] = np.c_[p.poi_lng, p.poi_lat, np.ones(len(p))] @ cx
    p["Y"] = np.c_[p.poi_lng, p.poi_lat, np.ones(len(p))] @ cy
    rng = np.random.default_rng(20261027)
    keys = []
    for (st, ds), g in p[p.ds.isin(fut)].groupby(["from_dipan_id", "ds"]):
        cnt = g.groupby("delivery_user_id").size()
        cs = sorted(cnt[cnt >= MIN_PICKUPS].index)
        rng.shuffle(cs)
        for j in range(len(cs) // TEAM):
            keys.append((st, int(ds), tuple(sorted(cs[TEAM * j:TEAM * (j + 1)]))))
    order = rng.permutation(len(keys))
    return p, [keys[i] for i in order]


def build(city, st, ds, team):
    p, _ = instances(city)
    g = p[(p.from_dipan_id == st) & (p.ds == ds) & p.delivery_user_id.isin(team)].copy()
    base = (pd.Timestamp(f"2022-{ds // 100:02d}-{ds % 100:02d}") - pd.Timestamp("2022-03-01")).total_seconds() + DAY0
    g["lo"] = (g.book_start_time_s - base).clip(lower=0)      # the promised window opens
    g["hi"] = g.expect_got_time_s - base
    g = g[g.hi > 0]
    G = g.groupby(["aoi_id", "book_start_time_s", "expect_got_time_s"]).agg(
        X=("X", "mean"), Y=("Y", "mean"), n=("order_id", "size"), lo=("lo", "max"), hi=("hi", "min")).reset_index()
    G["lo"] = np.minimum(G.lo, G.hi)
    dep = (G.X.mean(), G.Y.mean())                     # the team's centre
    xy = np.vstack([dep, G[["X", "Y"]].values])
    dist = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    real_late = bool((g.got_time_s > g.expect_got_time_s).any())
    return {"station": st, "ds": ds, "dist": dist, "extra": np.r_[0, G.n.values - 1],
            "lo": np.r_[0, G.lo.values], "hi": np.r_[SHIFT, G.hi.values],
            "fleet": TEAM, "orders": int(len(g)), "customers": int(len(G)), "real_late": real_late}


def nominal_times(inst, pools, factor=1.0):
    t = inst["dist"] * pools.nom_pace + pools.nom_still
    t = t + (inst["extra"][:, None] * pools.nom_extra)      # handling of further orders before leaving i
    np.fill_diagonal(t, 0)
    return np.ceil(t * factor).astype(int)


def solve(inst, times, hi):
    n = len(inst["lo"])
    m = Model()
    locs = [m.add_location(x=0, y=0) for _ in range(n)]
    depot = m.add_depot(location=locs[0], tw_early=0, tw_late=SHIFT)
    m.add_vehicle_type(inst["fleet"], capacity=[10 ** 6], start_depot=depot, end_depot=depot,
                       tw_early=0, tw_late=SHIFT, shift_duration=SHIFT, unit_distance_cost=1, unit_duration_cost=0)
    for i in range(1, n):
        m.add_client(location=locs[i], delivery=[1], service_duration=0,
                     tw_early=int(inst["lo"][i]), tw_late=int(max(inst["lo"][i], hi[i])))
    for i in range(n):
        for j in range(n):
            if i != j:
                m.add_edge(locs[i], locs[j], distance=int(times[i][j]), duration=int(times[i][j]))
    r = m.solve(stop=MaxIterations(ITER), seed=1, display=False)
    if not r.is_feasible():
        return None
    routes = [[int(a.idx) + 1 for a in rt if a.is_client()] for rt in r.best.routes()]
    routes = [rt for rt in routes if rt]
    deps = []
    for rt in routes:                                       # latest departure keeping every planned start in its window
        latest_next, nxt, latest = float(SHIFT), 0, {}
        for c in reversed(rt):
            latest[c] = min(float(hi[c]), latest_next - times[c][nxt])
            latest[c] = max(latest[c], float(inst["lo"][c]))
            latest_next, nxt = latest[c], c
        deps.append(max(0.0, latest[rt[0]] - times[0][rt[0]]))
    travel = float(sum(times[a][b] for rt in routes for a, b in zip([0] + rt, rt + [0])))
    return {"routes": routes, "departures": deps, "vehicles": len(routes), "travel": travel}


def simulate(inst, plan, pools, n, seed):
    """Share of simulated days on which every customer is picked up by the end of its window."""
    legs = max(len(rt) for rt in plan["routes"]) + 1
    ok = np.ones(n, bool)
    for r, (rt, dep) in enumerate(zip(plan["routes"], plan["departures"])):
        pace, still, extra = pools.draws(n, legs, seed + 7919 * r)
        t = np.full(n, float(dep))
        prev = 0
        for k, c in enumerate(rt):
            t = t + inst["dist"][prev][c] * pace[:, k] + still[:, k]
            start = np.maximum(t, inst["lo"][c])
            ok &= start <= inst["hi"][c] + 1e-9
            e = int(inst["extra"][c])
            t = start + (extra[:, k] * e if e else 0.0)    # further orders at the same stop
            prev = c
    return int(ok.sum()), n


def wilson_lower(k, n, z=ALPHA_SCREEN_Z):
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def run_one(city, k):
    _, keys = instances(city)
    st, ds, team = keys[k]
    out = OUT / city / f"{k:03d}.json"
    if out.exists():
        return f"{k} exists"
    hist_days, fut_days = periods()
    H, F = Pools(city, hist_days), Pools(city, fut_days)
    inst = build(city, st, ds, team)
    seed = 10_000 + k
    nom = nominal_times(inst, H)
    rec = {"city": city, "k": k, "station": st, "ds": ds, "orders": inst["orders"], "customers": inst["customers"],
           "fleet": inst["fleet"], "real_late": inst["real_late"], "configs": {}}

    def judge(plan):
        ks, ns = simulate(inst, plan, H, CERT_N, 200_000 + seed)
        kt, nt = simulate(inst, plan, F, TEST_N, 300_000 + seed)
        return {"vehicles": plan["vehicles"], "travel": plan["travel"], "cert_success": ks / ns,
                "certified": cp_lower(ks, ns) >= TARGET, "future_success": kt / nt,
                "fails_on_future": cp_lower(ks, ns) >= TARGET and cp_upper(kt, nt) < TARGET}

    plans = {"nominal": solve(inst, nom, inst["hi"]),
             "padding20": solve(inst, nominal_times(inst, H, 1.2), inst["hi"])}
    # earliest reachable start of each customer at nominal times: the cap of the buffers
    earliest = np.maximum(nom[0], inst["lo"])
    cands = []
    for beta in BETAS:
        hi = inst["hi"].astype(float).copy()
        hi[1:] = np.minimum(hi[1:], np.maximum.reduce([inst["lo"][1:], hi[1:] - 60 * beta, earliest[1:]]))
        pl = solve(inst, nom, hi)
        if pl is None:
            continue
        ks, ns = simulate(inst, pl, H, SCREEN_N, 100_000 + seed)
        cands.append((beta, pl, wilson_lower(ks, ns)))
    passing = [c for c in cands if c[2] >= 0.95]
    sel = min(passing, key=lambda c: (c[1]["travel"], c[0]))[1] if passing else plans["padding20"]
    plans["capped_screen"] = sel
    # fixed-order certification on the history certification draws
    certified = []
    for beta, pl, _ in sorted(cands, key=lambda c: -c[0]):
        ks, ns = simulate(inst, pl, H, CERT_N, 200_000 + seed)
        if cp_lower(ks, ns) < TARGET:
            break
        certified.append((pl["travel"], beta, pl))
    plans["fixed_order"] = min(certified, key=lambda c: (c[0], c[1]))[2] if certified else None
    for name, pl in plans.items():
        rec["configs"][name] = None if pl is None else judge(pl)
    rec["screen_selected"] = bool(passing)
    OUT.joinpath(city).mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec))
    return f"{k} {st[:6]} ds={ds} customers={inst['customers']} " + " ".join(
        f"{n}:{'-' if v is None else round(100 * v['future_success'], 1)}" for n, v in rec["configs"].items())


def summarise(city):
    R = [json.loads(f.read_text()) for f in sorted((OUT / city).glob("*.json"))]
    out = {"city": city, "instances": len(R), "configs": {}}
    for name in ("nominal", "padding20", "capped_screen", "fixed_order"):
        v = [r["configs"][name] for r in R]
        have = [x for x in v if x]
        out["configs"][name] = {
            "plans": len(have),
            "pooled_future": float(np.mean([100 * x["future_success"] if x else 0 for x in v])),
            "pooled_history": float(np.mean([100 * x["cert_success"] if x else 0 for x in v])),
            "certified": sum(x["certified"] for x in have),
            "fails_on_future": sum(x["fails_on_future"] for x in have),
            "vehicles": float(np.mean([x["vehicles"] for x in have])) if have else None}
    print(json.dumps(out, indent=1))
    (ROOT / "results" / f"lade_field_summary_{city}.json").write_text(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="yt")
    ap.add_argument("--instances", type=int, default=10)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.city not in lt.DEV_CITIES:
        raise SystemExit("only development cities may be analysed before the protocol is frozen")
    if a.summarise:
        return summarise(a.city)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, a.city, k): k for k in range(a.instances)}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[f]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
