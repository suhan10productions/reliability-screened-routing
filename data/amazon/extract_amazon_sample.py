"""Extract a reproducible sample of routes from the Amazon Last Mile Routing Research
Challenge training data (CC BY-NC 4.0) into one small JSON file.

Run on the computer that holds the data (standard library only, low memory):
  python3 extract_amazon_sample.py <data folder> <output folder>

Writes amazon_sample.json into the output folder (default: the data folder); gzip it to get
amazon_sample.json.gz. Selection: routes Amazon scored "High",
at most 5 per station, drawn with a fixed seed, so the sample can be rebuilt exactly.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

N_ROUTES = 60          # sampled routes (the study uses the first 40 that build; the rest are spares)
PER_STATION = 5
SEED = 20261019

_dec = json.JSONDecoder()


def items(path: Path, chunk: int = 1 << 23):
    """Yield (key, value) pairs of a top-level JSON object without loading the file.
    Python's json accepts the NaN values that appear in Amazon's files."""
    with open(path, encoding="utf-8") as f:
        buf = f.read(chunk)
        pos = buf.index("{") + 1
        while True:
            while True:
                k = buf.find('"', pos)
                if k >= 0:
                    break
                more = f.read(chunk)
                if not more:
                    return
                buf, pos = buf[pos:] + more, 0
            ke = buf.find('"', k + 1)
            colon = buf.find(":", ke) if ke >= 0 else -1
            if ke < 0 or colon < 0:
                buf, pos = buf[k:] + f.read(chunk), 0
                continue
            key, v = buf[k + 1:ke], colon + 1
            while True:
                start = v + len(buf[v:]) - len(buf[v:].lstrip())
                try:
                    val, end = _dec.raw_decode(buf, start)
                    break
                except json.JSONDecodeError:
                    more = f.read(chunk)
                    if not more:
                        raise
                    buf = buf[k:] + more
                    v, k = v - k, 0
            yield key, val
            pos = end
            if pos > chunk:
                buf, pos = buf[pos:], 0


def main():
    root = Path(sys.argv[1]).expanduser()
    dest_dir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else root
    routes = json.loads((root / "route_data.json").read_text())
    rng = random.Random(SEED)
    by_station = defaultdict(list)
    for rid in sorted(routes):
        if routes[rid]["route_score"] == "High":
            by_station[routes[rid]["station_code"]].append(rid)
    pool = []
    for st in sorted(by_station):
        ids = by_station[st][:]
        rng.shuffle(ids)
        pool += ids[:PER_STATION]
    rng.shuffle(pool)
    chosen = set(pool[:N_ROUTES])
    print(f"{len(by_station)} stations, {len(chosen)} routes chosen", flush=True)

    seqs = json.loads((root / "actual_sequences.json").read_text())
    out = {rid: {"route": routes[rid], "actual_sequence": seqs[rid]["actual"]} for rid in chosen}

    print("reading package_data.json ...", flush=True)
    for rid, stops in items(root / "package_data.json"):
        if rid in chosen:
            agg = {}
            for stop, pk in stops.items():
                svc = sum((p.get("planned_service_time_seconds") or 0.0) for p in pk.values())
                vol = sum(p["dimensions"]["depth_cm"] * p["dimensions"]["height_cm"] * p["dimensions"]["width_cm"]
                          for p in pk.values())
                tws = [(p["time_window"]["start_time_utc"], p["time_window"]["end_time_utc"]) for p in pk.values()
                       if isinstance(p["time_window"]["start_time_utc"], str)]
                agg[stop] = {"service_seconds": svc, "volume_cm3": vol, "packages": len(pk), "time_windows": tws}
            out[rid]["stops"] = agg

    print("reading travel_times.json (1.7 GB, a few minutes) ...", flush=True)
    found = 0
    for rid, matrix in items(root / "travel_times.json"):
        if rid in chosen:
            out[rid]["travel_seconds"] = matrix
            found += 1
            print(f"  {found}/{len(chosen)}", flush=True)
            if found == len(chosen):
                break

    meta = {"source": "Amazon Last Mile Routing Research Challenge, training data (almrrc2021), CC BY-NC 4.0",
            "selection": f"route_score High, at most {PER_STATION} per station, seed {SEED}, {N_ROUTES} routes",
            "routes": out}
    dest = dest_dir / "amazon_sample.json"
    dest.write_text(json.dumps(meta))
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
