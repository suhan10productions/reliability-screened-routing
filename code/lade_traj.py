"""Travel and handling times from LaDe courier trajectories (exploratory development).

Inputs (data/lade/): the trajectory period's pickup orders (traj/pickup_five_cities.parquet,
21 March to 20 April 2022) and the courier GPS trajectories converted by
code/lade_traj_extract.py and sorted by courier and time (traj_raw/sorted_*.npy; positions in
metres of a projected system, about every 20 seconds).

For every pair of consecutive pickups of one courier on one day, the courier's track between
the two pickup scans gives
  straight   distance between the courier's positions at the two scans (m),
  path       length of the track between them (m),
  moving     seconds spent between GPS points at more than MOVE_MS metres per second,
  still      the other seconds.
A leg is DIRECT when the track does not detour (path <= DETOUR * straight + SLACK_M): the
courier went from one pickup to the next. On direct legs the moving time measures travel,
which depends on distance and traffic rather than on the courier's choices; the still time
measures handling and waiting at the stop. Legs with gaps in the track (a step longer than
MAX_STEP_S) are dropped.

Usage (from the package root), development city only:
  PYTHONPATH=code python code/lade_traj.py --city yt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "lade"
CITY = {"yt": "烟台市", "hz": "杭州市", "cq": "重庆市", "sh": "上海市", "jl": "吉林市"}
MOVE_MS = 1.0
DETOUR, SLACK_M = 1.5, 150.0
MAX_STEP_S = 90
DEV_CITIES = ("yt",)


def load_tracks():
    c = np.load(D / "traj_raw" / "sorted_c.npy")
    t = np.load(D / "traj_raw" / "sorted_t.npy")
    x = np.load(D / "traj_raw" / "sorted_x.npy", mmap_mode="r")
    y = np.load(D / "traj_raw" / "sorted_y.npy", mmap_mode="r")
    starts = np.searchsorted(c, np.arange(c.max() + 2))
    return c, t, x, y, starts


def pickups(city: str) -> pd.DataFrame:
    p = pd.read_parquet(D / "traj" / "pickup_five_cities.parquet")
    p = p[p.from_city_name == CITY[city]].copy()
    ids = pd.read_parquet(D / "traj_raw" / "traj_couriers.parquet")
    code = dict(zip(ids.postman_id, ids.courier))
    for col in ("accept_time", "book_start_time", "expect_got_time", "got_time"):
        ts = pd.to_datetime("2022-" + p[col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        p[col + "_s"] = (ts - pd.Timestamp("2022-03-01")).dt.total_seconds()
    p["courier"] = p.delivery_user_id.map(code)
    return p


def legs(city: str) -> pd.DataFrame:
    p = pickups(city)
    p = p[p.courier.notna() & p.got_time_s.notna()].copy()
    p["courier"] = p.courier.astype(int)
    c, t, x, y, starts = load_tracks()
    rows = []
    for (cc, ds), g in p.sort_values("got_time_s").groupby(["courier", "ds"]):
        a, b = starts[cc], starts[cc + 1]
        if b - a < 10:
            continue
        tt = t[a:b]
        xx = np.asarray(x[a:b], dtype=np.float64)
        yy = np.asarray(y[a:b], dtype=np.float64)
        times = g.got_time_s.values
        aois = g.aoi_id.values
        for k in range(1, len(times)):
            t0, t1 = times[k - 1], times[k]
            if t1 <= t0:
                continue
            i0, i1 = np.searchsorted(tt, t0), np.searchsorted(tt, t1, side="right")
            if i1 - i0 < 2 or abs(tt[min(i0, len(tt) - 1)] - t0) > 60 or abs(tt[i1 - 1] - t1) > 60:
                continue
            st = np.diff(tt[i0:i1])
            if st.max() > MAX_STEP_S:
                continue
            step = np.hypot(np.diff(xx[i0:i1]), np.diff(yy[i0:i1]))
            mv = (step / np.maximum(st, 1)) > MOVE_MS
            straight = float(np.hypot(xx[i1 - 1] - xx[i0], yy[i1 - 1] - yy[i0]))
            rows.append({"courier": int(cc), "ds": int(ds), "t0": float(t0), "t1": float(t1),
                         "same_aoi": bool(aois[k] == aois[k - 1]), "straight": straight,
                         "path": float(step.sum()), "moving": float(st[mv].sum()), "still": float(st[~mv].sum()),
                         "gap": float(t1 - t0)})
    L = pd.DataFrame(rows)
    L["direct"] = L.path <= DETOUR * L.straight + SLACK_M
    L["hour"] = ((L.t0 % 86400) // 3600).astype(int)
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="yt")
    a = ap.parse_args()
    if a.city not in DEV_CITIES:
        raise SystemExit("only development cities may be analysed before the protocol is frozen")
    L = legs(a.city)
    L.to_parquet(ROOT / "results" / f"lade_traj_legs_{a.city}.parquet")
    X = L[L.direct & ~L.same_aoi & (L.straight > 100)]
    out = {"city": a.city, "legs": len(L), "direct_share": float(L.direct.mean()),
           "direct_cross_legs": len(X),
           "gap_min_q": (L.gap.quantile([.25, .5, .75, .9]) / 60).round(1).tolist(),
           "direct_gap_min_q": (X.gap.quantile([.25, .5, .75, .9]) / 60).round(1).tolist(),
           "direct_moving_speed_ms_q": (X.straight / X.moving.clip(lower=20)).quantile([.1, .25, .5, .75, .9]).round(2).tolist(),
           "direct_still_min_q": (X.still.quantile([.25, .5, .75, .9]) / 60).round(1).tolist()}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
