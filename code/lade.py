"""Real pickup routes with real time windows: the LaDe-P data set (exploratory development).

Data: LaDe-P, the pickup part of the LaDe last-mile data set released by Cainiao
(Wu et al. 2023, https://huggingface.co/datasets/Cainiao-AI/LaDe-P, Apache-2.0),
one Parquet file per city in data/lade/. Each row is one pickup order: the
customer's two-hour pickup window, the time the courier accepted the order, the
time it was picked up, the order's location (perturbed by about 10 m for
privacy), its area of interest (AOI), the courier and the day, May to October 2022.

Everything here is estimated from the data; nothing is assumed:

  stop-to-stop time   the time between two consecutive pickups of one courier on
                      one day. It contains the travel, the handling of the order
                      and whatever else the courier did in between (deliveries,
                      breaks), so it is the effective time a planner faces. Gaps
                      longer than MAX_GAP minutes are treated as breaks and dropped.
  nominal time        the median stop-to-stop time as a function of the straight-
                      line distance (piecewise linear in distance bins), for legs
                      between different AOIs; extra orders at the same stop take
                      the median time between consecutive pickups in one AOI.
  a simulated day     replays one real day of the history: a day is drawn, each
                      route is given one real courier-day of that day, and every
                      leg of the route draws its time from that courier-day's own
                      legs (ratio to the nominal time), so a slow courier-day stays
                      slow for the whole route and a slow day affects every route.

A customer is one AOI and window on one region-day; its earliest pickup is the
time its last order was accepted (couriers may pick up before the window opens,
as in the data), and it is late if its first pickup is after the window ends.

Usage (from the package root), development city only:
  PYTHONPATH=code python code/lade.py --city jl --calibrate
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "lade"
DAY_START = 7 * 60          # minutes after midnight that are time 0 (07:00)
DAY_END = 21 * 60
MAX_GAP = 90.0              # minutes; longer gaps between pickups are breaks
KM_EDGES = np.array([0.0, 0.2, 0.4, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0])
MIN_LEGS = 5                # a courier-day enters the history with at least this many legs between AOIs
TRAIN_MONTHS = (5, 6, 7, 8)
TEST_MONTHS = (9, 10)


def hav(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


@lru_cache(maxsize=4)
def load(city: str) -> pd.DataFrame:
    d = pd.read_parquet(DATA / f"pickup_{city}.parquet")
    for c in ("accept_time", "time_window_start", "time_window_end", "pickup_time"):
        t = pd.to_datetime("2022-" + d[c], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        day = pd.to_datetime("2022-" + d["ds"].astype(str).str.zfill(4), format="%Y-%m%d")
        d[c + "_min"] = (t - day).dt.total_seconds() / 60.0 - DAY_START   # minutes after 07:00 of the order's day
    d["month"] = d["ds"] // 100
    return d


def legs(d: pd.DataFrame) -> pd.DataFrame:
    """Consecutive pickups of one courier on one day."""
    d = d.sort_values(["courier_id", "ds", "pickup_time_min", "order_id"])
    g = d.groupby(["courier_id", "ds"], sort=False)
    prev = {c: g[c].shift() for c in ("lat", "lng", "pickup_time_min", "aoi_id")}
    L = pd.DataFrame({"courier_id": d.courier_id, "ds": d.ds, "month": d.month, "region_id": d.region_id,
                      "t0": prev["pickup_time_min"], "t1": d.pickup_time_min,
                      "km": hav(prev["lat"], prev["lng"], d.lat, d.lng),
                      "cross": d.aoi_id != prev["aoi_id"]}).dropna(subset=["t0"])
    L["minutes"] = L.t1 - L.t0
    L = L[(L.minutes > 0) & (L.minutes <= MAX_GAP)]
    L["hour"] = ((L.t0 + DAY_START) // 60).astype(int)
    return L


@dataclass
class History:
    """Stop-to-stop times learned from the legs of a set of days."""
    km_mid: np.ndarray          # bin midpoints
    km_med: np.ndarray          # median minutes in each bin (legs between AOIs)
    same_med: float             # median minutes between pickups in one AOI
    days: np.ndarray            # the days in the history
    cd_day: np.ndarray          # day of each courier-day
    cross_off: np.ndarray       # offsets of each courier-day's log ratios in cross_pool
    cross_len: np.ndarray
    cross_pool: np.ndarray      # log(minutes / nominal) of legs between AOIs, grouped by courier-day
    same_off: np.ndarray
    same_len: np.ndarray
    same_pool: np.ndarray       # minutes between pickups in one AOI, grouped by courier-day
    day_cds: dict               # day -> indices of its courier-days

    def nominal(self, km):
        return np.interp(np.asarray(km, float), self.km_mid, self.km_med)

    @classmethod
    def fit(cls, L: pd.DataFrame) -> "History":
        X = L[L.cross & (L.km < KM_EDGES[-1])]
        b = np.clip(np.digitize(X.km, KM_EDGES) - 1, 0, len(KM_EDGES) - 2)
        med = X.groupby(b).minutes.median().reindex(range(len(KM_EDGES) - 1)).interpolate().bfill().ffill().values
        mid = (KM_EDGES[:-1] + KM_EDGES[1:]) / 2
        mid[0] = 0.0
        med = np.maximum.accumulate(med)            # nominal time does not fall with distance
        same = L[~L.cross]
        hist = cls(mid, med, float(same.minutes.median()), np.array([]), *([np.array([])] * 7), {})
        X = L[L.cross].copy()
        X["lr"] = np.log(X.minutes / hist.nominal(X.km.clip(upper=KM_EDGES[-1])))
        cnt = X.groupby(["courier_id", "ds"]).size()
        keep = cnt[cnt >= MIN_LEGS].index
        X = X.set_index(["courier_id", "ds"]).loc[keep].sort_index()
        S = same.set_index(["courier_id", "ds"])
        cds = list(keep)
        cross_len = np.array([cnt[k] for k in cds])
        cross_off = np.concatenate([[0], np.cumsum(cross_len)[:-1]])
        same_groups = S.groupby(level=[0, 1]).minutes.apply(np.asarray)
        same_arrays = [same_groups.get(k, np.array([])) for k in cds]
        same_len = np.array([len(a) for a in same_arrays])
        same_off = np.concatenate([[0], np.cumsum(same_len)[:-1]])
        cd_day = np.array([k[1] for k in cds])
        days = np.unique(cd_day)
        hist.days, hist.cd_day = days, cd_day
        hist.cross_pool = X.lr.values
        hist.cross_off, hist.cross_len = cross_off, cross_len
        hist.same_pool = np.concatenate(same_arrays) if same_arrays else np.array([])
        hist.same_off, hist.same_len = same_off, same_len
        hist.day_cds = {int(dd): np.flatnonzero(cd_day == dd) for dd in days}
        return hist

    def summary(self):
        return {"days": int(len(self.days)), "courier_days": int(len(self.cd_day)), "legs": int(len(self.cross_pool)),
                "km_mid": self.km_mid.round(3).tolist(), "nominal_minutes": self.km_med.round(2).tolist(),
                "same_aoi_minutes": self.same_med}


class DayDraws:
    """Random days for a plan: day, courier-day per route, and leg draws."""

    def __init__(self, hist: History, n: int, seed: int, routes: int):
        rng = np.random.default_rng(seed)
        self.hist, self.rng = hist, rng
        day = rng.choice(hist.days, size=n)
        self.cd = np.empty((n, routes), dtype=int)
        for dd in np.unique(day):
            idx = np.flatnonzero(day == dd)
            pool = hist.day_cds[int(dd)]
            self.cd[idx] = rng.choice(pool, size=(len(idx), routes))

    def cross(self, r: int):
        h, cd = self.hist, self.cd[:, r]
        u = self.rng.random(len(cd))
        return np.exp(h.cross_pool[h.cross_off[cd] + (u * h.cross_len[cd]).astype(int)])

    def same(self, r: int, k: int):
        """Total minutes for k further orders at one stop."""
        if k <= 0:
            return 0.0
        h, cd = self.hist, self.cd[:, r]
        tot = np.zeros(len(cd))
        has = h.same_len[cd] > 0
        for _ in range(k):
            u = self.rng.random(len(cd))
            v = np.full(len(cd), h.same_med)
            j = h.same_off[cd[has]] + (u[has] * h.same_len[cd[has]]).astype(int)
            v[has] = h.same_pool[j]
            tot += v
        return tot


def simulate_route(stops, km, extra, lo, hi, depart, draws: DayDraws, r: int, depot_km=None):
    """Lateness of one route on every simulated day.

    stops: customer indices in order; km[i][j] distances; extra[i] further orders at customer i;
    lo, hi: earliest pickup and window end; depart: departure time from the first point.
    If depot_km is None the route starts at its first customer at time `depart` (a real courier's route).
    Returns a boolean array: True where some customer on the route was late.
    """
    h = draws.hist
    n = draws.cd.shape[0]
    late = np.zeros(n, bool)
    t = np.full(n, float(depart))
    prev = None
    for k, c in enumerate(stops):
        if prev is None and depot_km is None:
            start = np.maximum(t, lo[c])
        else:
            d = depot_km[c] if prev is None else km[prev][c]
            t = t + h.nominal(d) * draws.cross(r)
            start = np.maximum(t, lo[c])
        late |= start > hi[c] + 1e-9
        t = start + draws.same(r, extra[c])
        prev = c
    return late


def calibrate(city: str, min_orders: int = 5, n_days: int = 1000, seed: int = 20261027):
    """Real courier-days of the test months: model-predicted chance of a late pickup against what happened."""
    d = load(city)
    L = legs(d)
    hist = History.fit(L[L.month.isin(TRAIN_MONTHS)])
    test = d[d.month.isin(TEST_MONTHS)]
    rows = []
    for (cid, ds), g in test.groupby(["courier_id", "ds"]):
        if len(g) < min_orders:
            continue
        g = g.sort_values(["pickup_time_min", "order_id"])
        # customers = runs of consecutive orders in one AOI, in the courier's real order
        blocks = []
        for _, o in g.iterrows():
            if blocks and blocks[-1]["aoi"] == o.aoi_id:
                b = blocks[-1]
                b["n"] += 1
                b["lo"] = max(b["lo"], o.accept_time_min)
                b["hi"] = min(b["hi"], o.time_window_end_min)
            else:
                blocks.append({"aoi": o.aoi_id, "lat": o.lat, "lng": o.lng, "n": 1,
                               "lo": o.accept_time_min, "hi": o.time_window_end_min})
        m = len(blocks)
        lat = np.array([b["lat"] for b in blocks]); lng = np.array([b["lng"] for b in blocks])
        km = hav(lat[:, None], lng[:, None], lat[None, :], lng[None, :])
        lo = np.array([b["lo"] for b in blocks]); hi = np.array([b["hi"] for b in blocks])
        extra = [b["n"] - 1 for b in blocks]
        draws = DayDraws(hist, n_days, seed + int(cid) * 1000 + int(ds), 1)
        late = simulate_route(list(range(m)), km, extra, lo, hi, float(g.pickup_time_min.iloc[0]), draws, 0)
        rows.append({"courier_id": int(cid), "ds": int(ds), "orders": len(g), "stops": m,
                     "predicted_late": float(late.mean()),
                     "observed_late": bool((g.pickup_time_min > g.time_window_end_min).any())})
    R = pd.DataFrame(rows)
    out = {"city": city, "history": hist.summary(), "courier_days": len(R),
           "observed_late_share": float(R.observed_late.mean()), "predicted_late_mean": float(R.predicted_late.mean())}
    R["bin"] = pd.qcut(R.predicted_late.rank(method="first"), 10, labels=False)
    out["deciles"] = R.groupby("bin").agg(pred=("predicted_late", "mean"), obs=("observed_late", "mean"),
                                         n=("observed_late", "size")).round(4).to_dict("records")
    p = ROOT / "results" / f"lade_calibration_{city}.json"
    p.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "history"}, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="jl")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    if a.city != "jl":
        raise SystemExit("only the development city (jl) may be analysed before the protocol is frozen")
    if a.calibrate:
        calibrate(a.city)


if __name__ == "__main__":
    main()
