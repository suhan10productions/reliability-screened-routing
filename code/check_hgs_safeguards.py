"""Demonstrate the protocol-2 safeguards without touching the repository.

Relabels the development records of both generators (OR-Tools stage 1 and
stage 2, and results/hgs_dev) onto the prescribed protocol-2 seeds, purely to
exercise the validator; the numbers it prints are NOT results. The complete
fixture must pass and every tampering case must be rejected with a protocol
violation. Uses the running interpreter.

Run from the package root:  python code/check_hgs_safeguards.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "code")
from confirm_analysis_hgs import MANIFEST_FILES, SEED_SHIFT  # noqa: E402

TMP = Path(tempfile.mkdtemp())
MANIFEST = TMP / "manifest.json"
S1_KEYS = ("static", "peak_aware_distance", "weighted_objective_only", "fleet_matched_distance")


def build(mutate_hgs=None, mutate_s2=None, extra=None):
    out = TMP / "study"
    shutil.rmtree(out, ignore_errors=True)
    (out / "v7").mkdir(parents=True)
    (out / "hgs").mkdir()
    stage1 = []
    for n in (20, 50, 100, 200):
        d = json.loads(Path(f"results/study_v6_n{n}.json").read_text())
        new = {"schema": d["schema"], "environment": d["environment"], "records": [], "software_errors": []}
        for r in d["records"]:
            dev = r["instance_seed"]
            s = dev + SEED_SHIFT
            r.update(instance_seed=s, screening_seed=100_000 + s, validation_seed=200_000 + s)
            st = {k: ("ok" if r[k]["plan"] is not None else "no_plan: fixture") for k in S1_KEYS}
            r["configuration_status"] = {**st, "anchors": "ok", "screened": "ok"}
            new["records"].append(r)
            v = json.loads(Path(f"results/v7/instance_{dev}.json").read_text())
            v.update(instance_seed=s, screening_seed=100_000 + s, validation_seed=400_000 + s,
                     sensitivity_seed=500_000 + s)
            v["configuration_status"] = {c: ("ok" if x is not None else "no_plan: fixture")
                                         for c, x in v["configurations"].items()}
            v["source_record_sha256"] = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
            if mutate_s2:
                mutate_s2(s, v)
            (out / "v7" / f"instance_{s}.json").write_text(json.dumps(v))
        p = out / f"s1_{n}.json"
        p.write_text(json.dumps(new))
        stage1.append(str(p))
    for f in sorted(Path("results/hgs_dev").glob("instance_*.json")):
        r = json.loads(f.read_text())
        s = r["instance_seed"] + SEED_SHIFT
        r.update(instance_seed=s, screening_seed=100_000 + s, validation_seed=400_000 + s, hgs_seed=s)
        r["environment"] = {**r["environment"], "pyvrp": "0.14.0", "ortools": "9.15.6755", "numpy": "2.5.3"}
        if mutate_hgs:
            mutate_hgs(s, r)
        (out / "hgs" / f"instance_{s}.json").write_text(json.dumps(r))
    if extra:
        extra(out)
    return stage1, out


def run(stage1, out):
    env = dict(os.environ, PYTHONPATH="code")
    p = subprocess.run([sys.executable, "code/confirm_analysis_hgs.py", "confirmatory", "--stage1", *stage1,
                        "--stage2", str(out / "v7"), "--hgs", str(out / "hgs"), "--manifest", str(MANIFEST)],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0 and not p.stderr.startswith("PROTOCOL VIOLATION"):
        print(p.stderr)
        raise SystemExit("analysis crashed; see traceback above")
    return p.returncode, (p.stdout if p.returncode == 0 else p.stderr).strip()


def main():
    if len(list(Path("results/hgs_dev").glob("instance_*.json"))) != 53:
        raise SystemExit("results/hgs_dev must hold all 53 development records")
    MANIFEST.write_text(json.dumps({f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
                                    for f in MANIFEST_FILES}))
    ok = True
    code, out = run(*build())
    ok &= code == 0
    print(f"{'PASS expected':16s} complete study (both generators) -> exit {code}")
    first = 7200 + SEED_SHIFT

    def at(seed, fn):
        return lambda s, r: fn(r) if s == seed else None

    def drop_customer(r):
        c = next(k for k, v in r["configurations"].items() if v)
        next(rt for rt in r["configurations"][c]["plan"]["routes"] if len(rt) > 2).pop(1)

    cases = {
        "HGS instance missing": dict(extra=lambda o: (o / "hgs" / f"instance_{first}.json").unlink()),
        "HGS unexpected file": dict(extra=lambda o: (o / "hgs" / "notes.json").write_text("{}")),
        "HGS duplicate record": dict(extra=lambda o: shutil.copy(o / "hgs" / f"instance_{first}.json",
                                                                 o / "hgs" / f"instance_{first}_copy.json")),
        "HGS software error": dict(extra=lambda o: (o / "hgs" / f"software_error_{first}.json").write_text(
            json.dumps({"instance_seed": first, "error": "TypeError: x"}))),
        "HGS iteration budget": dict(mutate_hgs=at(first + 1, lambda r: r.update(hgs_iterations=5000))),
        "HGS validation scenarios": dict(mutate_hgs=at(first + 2, lambda r: next(
            v for v in r["configurations"].values() if v)["validation"].update(scenarios=500))),
        "HGS validation seed": dict(mutate_hgs=at(first + 3, lambda r: r.update(validation_seed=1))),
        "HGS pyvrp version": dict(mutate_hgs=at(first + 4, lambda r: r["environment"].update(pyvrp="0.13.0"))),
        "HGS plan null, status ok": dict(mutate_hgs=at(first + 5, lambda r: r["configurations"].update(
            hgs_capped_cons=None))),
        "HGS plan skips a customer": dict(mutate_hgs=at(first + 6, drop_customer)),
        "HGS wrong size": dict(mutate_hgs=at(first + 7, lambda r: r.update(customers=50))),
        "OR-Tools instance missing": dict(extra=lambda o: (o / "v7" / f"instance_{first}.json").unlink()),
        "OR-Tools budget changed": dict(mutate_s2=at(first + 8, lambda v: v.update(candidate_seconds=1.0))),
        "OR-Tools provenance swapped": dict(mutate_s2=at(first + 9, lambda v: v.update(
            source_record_sha256="0" * 64))),
    }
    for name, kw in cases.items():
        code, out = run(*build(**kw))
        ok &= code == 1
        print(f"{'REJECT expected':16s} {name:32s} -> exit {code} | {out[:76]}")
    for target in (Path("code/study_hgs.py"), Path("code/study_v6.py")):
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"\n# edited after freeze\n")
            code, out = run(*build())
        finally:
            target.write_bytes(original)
        ok &= code == 1
        print(f"{'REJECT expected':16s} {target.name + ' edited after freeze':32s} -> exit {code} | {out[:76]}")
    shutil.rmtree(TMP)
    print("ALL SAFEGUARDS BEHAVE AS SPECIFIED" if ok else "SAFEGUARD FAILURE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
