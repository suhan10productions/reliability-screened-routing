"""Convert LaDe's courier trajectory pickle to Parquet without loading it (memory-light).

courier_detailed_trajectory_20s.pkl.xz is a pickled pandas DataFrame of about
51 million GPS points (ds, postman_id, gps_time, lat, lng). Unpickling it needs
far more memory than this machine has, because the two text columns become
about 100 million Python strings. This script never unpickles: it walks the
pickle opcodes (pickletools.genops, which executes nothing), keeps each
distinct string once, and records the numeric buffers as they pass. Only the
opcode stream is read, so no code in the file can run.

Usage:
  python3 -I code/lade_traj_extract.py data/lade/traj_raw/traj.pkl.xz data/lade/traj_raw/traj.parquet
"""
import lzma
import pickletools
import sys

import numpy as np
import pandas as pd

STR_OPS = {"SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "UNICODE"}
GET_OPS = {"BINGET", "LONG_BINGET", "GET"}
BUF_OPS = {"BYTEARRAY8", "BINBYTES8", "BINBYTES", "SHORT_BINBYTES"}


def main(src, dst):
    uniq, table = {}, []
    memo = np.full(1 << 20, -1, dtype=np.int32)
    midx = 0
    lists, cur, in_list = [], None, False
    buffers = []
    last_code = None
    for k, (op, arg, _) in enumerate(pickletools.genops(lzma.open(src))):
        name = op.name
        code = None
        if name in STR_OPS:
            code = uniq.get(arg)
            if code is None:
                code = uniq[arg] = len(table)
                table.append(arg)
        elif name in GET_OPS:
            code = int(memo[arg]) if arg < len(memo) and memo[arg] >= 0 else None
        if name == "MEMOIZE":
            if midx >= len(memo):
                memo = np.concatenate([memo, np.full(len(memo), -1, dtype=np.int32)])
            memo[midx] = -1 if last_code is None else last_code
            midx += 1
            continue
        last_code = code
        if name == "EMPTY_LIST":
            cur, in_list = [], True
            continue
        if in_list:
            if code is not None:
                cur.append(code)
                if len(cur) >= 1 << 22:              # spill to compact arrays
                    lists.append(("part", np.array(cur, dtype=np.int32)))
                    cur = []
                continue
            if name in ("MARK", "APPENDS", "APPEND", "FRAME"):
                continue
            # the list has ended
            lists.append(("end", np.array(cur, dtype=np.int32)))
            cur, in_list = None, False
        if name in BUF_OPS and len(arg) > 1_000_000:
            buffers.append(arg)
        if k % 20_000_000 == 0:
            print(k, "ops", len(table), "distinct strings", flush=True)
    # join spilled parts into whole lists
    whole, acc = [], []
    for kind, arr in lists:
        acc.append(arr)
        if kind == "end":
            whole.append(np.concatenate(acc) if acc else np.array([], np.int32))
            acc = []
    big = [w for w in whole if len(w) > 1_000_000]
    small = [w for w in whole if 1 < len(w) <= 20]
    print("lists", [len(w) for w in whole if len(w) > 10], "buffers", [len(b) for b in buffers], flush=True)
    assert len(big) == 1, "expected one object block"
    codes = big[0]
    del whole, lists
    n = len(codes) // 2
    rows = codes.reshape(2, n)
    names = [[table[c] for c in w] for w in small]
    print("short lists (column names?)", names[-3:], flush=True)
    ints = [np.frombuffer(b, dtype="<i8") for b in buffers if len(b) == 8 * n]
    floats = [np.frombuffer(b, dtype="<f8") for b in buffers if len(b) == 16 * n]
    assert len(ints) == 1 and len(floats) == 1, [len(b) for b in buffers]
    fl = floats[0].reshape(2, n)
    # which object row holds the time: its strings look like "MM-DD HH:MM:SS"
    looks_time = lambda c: len(table[c]) == 14 and table[c][2] == "-"  # noqa: E731
    trow = 0 if looks_time(int(rows[0, 0])) else 1
    prow = 1 - trow
    # seconds since 1 March for each distinct string used as a time
    used = np.unique(rows[trow])
    sec = np.full(len(table), -1, dtype=np.int64)
    ts = pd.to_datetime(pd.Series([table[c] for c in used]).radd("2022-"), format="%Y-%m-%d %H:%M:%S", errors="coerce")
    sec[used] = ((ts - pd.Timestamp("2022-03-01")).dt.total_seconds().fillna(-1)).astype(np.int64).values
    pid_used, pid_code = np.unique(rows[prow], return_inverse=True)
    print("sample", table[int(rows[prow, 0])], table[int(rows[trow, 0])], fl[:, 0], ints[0][0], flush=True)
    df = pd.DataFrame({"ds": ints[0].astype(np.int16), "courier": pid_code.astype(np.int32),
                       "t": sec[rows[trow]].astype(np.int32), "x0": fl[0], "x1": fl[1]})
    df.to_parquet(dst)
    pd.DataFrame({"courier": np.arange(len(pid_used)), "postman_id": [table[c] for c in pid_used]}).to_parquet(
        dst.replace(".parquet", "_couriers.parquet"))
    print("rows", n, "couriers", len(pid_used), "wrote", dst, flush=True)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
