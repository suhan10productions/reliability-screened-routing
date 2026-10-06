"""Check the confirmatory safeguards without touching the repository.

Builds synthetic "fresh" studies by relabelling the development records onto
the prescribed confirmatory seeds, purely to exercise the validator. The
numbers it prints are NOT results. Two studies must pass (complete; and one
with a per-configuration no-plan outcome), and every tampering or failure case
must be rejected. Uses the running interpreter and environment.

Run from the package root:  python code/check_confirmatory_safeguards.py
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "code")
from confirm_analysis import MANIFEST_FILES  # noqa: E402

SHIFT = 60000
TMP = Path(tempfile.mkdtemp())
MANIFEST = TMP / "manifest.json"
S1_KEYS = ("static", "peak_aware_distance", "weighted_objective_only", "fleet_matched_distance")


def write_manifest():
    MANIFEST.write_text(json.dumps(
        {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in MANIFEST_FILES}))


def s1_status(r):
    st = {k: ("ok" if r[k]["plan"] is not None else "no_plan: synthetic") for k in S1_KEYS}
    st["anchors"] = "ok"
    st["screened"] = "ok"
    return st


def build(mutate_s1=None, mutate_s2=None, extra=None):
    """Relabel development records onto the fresh seeds, then apply mutations."""
    out = TMP / "study"
    shutil.rmtree(out, ignore_errors=True)
    (out / "v7").mkdir(parents=True)
    paths = []
    for n in (20, 50, 100, 200):
        d = json.loads(Path(f"results/study_v6_n{n}.json").read_text())
        new = {"schema": d["schema"], "environment": d["environment"],
               "records": [], "software_errors": []}
        for r in d["records"]:
            r = copy.deepcopy(r)
            dev = r["instance_seed"]
            s = dev + SHIFT
            r.update(instance_seed=s, screening_seed=100_000 + s, validation_seed=200_000 + s)
            r["configuration_status"] = s1_status(r)
            if mutate_s1:
                mutate_s1(s, r, new)
            new["records"].append(r)
            v = json.loads(Path(f"results/v7/instance_{dev}.json").read_text())
            v.update(instance_seed=s, screening_seed=100_000 + s,
                     validation_seed=400_000 + s, sensitivity_seed=500_000 + s)
            v["configuration_status"] = {c: ("ok" if x is not None else "no_plan: synthetic")
                                         for c, x in v["configurations"].items()}
            if mutate_s2:
                mutate_s2(s, v, r)
            v["source_record_sha256"] = hashlib.sha256(
                json.dumps(r, sort_keys=True).encode()).hexdigest()
            if mutate_s2 and getattr(mutate_s2, "after_hash", False):
                mutate_s2(s, v, r, after=True)
            (out / "v7" / f"instance_{s}.json").write_text(json.dumps(v))
        p = out / f"s1_{n}.json"
        p.write_text(json.dumps(new))
        paths.append(str(p))
    if extra:
        extra(out)
    return paths, out / "v7"


def run(paths, v7):
    env = dict(os.environ, PYTHONPATH="code")
    proc = subprocess.run(
        [sys.executable, "code/confirm_analysis.py", "confirmatory", "--stage1", *paths,
         "--stage2", str(v7), "--manifest", str(MANIFEST)],
        capture_output=True, text=True, env=env)
    # A rejection is a ProtocolViolation message. Anything else with a non-zero
    # exit (for example an unhandled exception, which also exits with 1) is a
    # crash: show it in full before any parsing, and never count it as a pass.
    if proc.returncode != 0 and not proc.stderr.startswith("PROTOCOL VIOLATION"):
        print(proc.stderr)
        raise SystemExit(f"analysis crashed (exit {proc.returncode}); see traceback above")
    return proc.returncode, (proc.stdout if proc.returncode == 0 else proc.stderr).strip()


def fleet_no_plan(s, r, new):
    """Per-configuration no-plan outcome: only fleet-matched fails at stage 1."""
    if s == 67203:
        r["fleet_matched_distance"]["plan"] = None
        r["fleet_matched_distance"]["validation"] = None
        r["configuration_status"]["fleet_matched_distance"] = "no_plan: fleet-matched distance solve"


def fleet_no_plan_s2(s, v, r):
    if s == 67203:
        v["configurations"]["fleet_matched"] = None
        v["configuration_status"]["fleet_matched"] = "no_plan: fleet-matched distance solve"


def main():
    ok = True
    write_manifest()

    code, out = run(*build())
    good = code == 0 and "CONFIRMATORY" in out
    ok &= good
    o = json.loads(out) if code == 0 else {}
    print(f"{'PASS expected':34s} complete study              -> exit {code}")
    if code == 0:
        same = o["H4_noise_growth"]["k"] == o["H1_P_minus_C"]["k"]
        ok &= same
        print(f"{'':34s} H4 uses H1's subset: {same} (k = {o['H1_P_minus_C']['k']})")

    code, out = run(*build(mutate_s1=fleet_no_plan, mutate_s2=fleet_no_plan_s2))
    ok &= code == 0
    if code == 0:
        o = json.loads(out)
        kept = o["common_subset"] == 46
        ok &= kept
        print(f"{'PASS expected':34s} fleet-matched has no plan   -> exit {code}; "
              f"other configurations kept, H1 subset still {o['common_subset']}: {kept}")
    else:
        print("per-configuration no-plan study wrongly rejected:", out[:150])

    def dup(out_dir):
        shutil.copy(out_dir / "v7" / "instance_67200.json", out_dir / "v7" / "instance_67200_copy.json")

    def stage1_software_error(s, r, new):
        if s == 67201:
            new["software_errors"].append({"customers": 20, "instance_seed": 67299,
                                           "stage": 1, "error": "KeyError: 'x'"})

    def s2_error_file(out_dir):
        (out_dir / "v7" / "software_error_67204.json").write_text(json.dumps(
            {"customers": 20, "instance_seed": 67204, "stage": 2, "error": "TypeError: y"}))

    def wrong_s1_validation_seed(s, r, new):
        if s == 67205:
            r["validation_seed"] = 123   # provenance hash is recomputed after this

    def missing_cell(s, v, r):
        if s == 67206:
            v["configurations"]["procedure"]["sensitivity"].pop("0.20,0.5")

    def silently_null(s, v, r):
        if s == 67207:
            v["configurations"]["capped_procedure"] = None   # status left as "ok"

    def dropped(s, v, r):
        if s == 67211:
            v["configurations"].pop("capped_procedure")

    def budget(s, v, r):
        if s == 67208:
            v["candidate_seconds"] = 1.0

    def scenarios(s, v, r):
        if s == 67209:
            v["configurations"]["procedure"]["validation"]["scenarios"] = 500

    def wrong_s2_seed(s, v, r):
        if s == 67210:
            v["validation_seed"] = 123

    def swapped(s, v, r, after=False):
        if after and s == 67212:
            v["source_record_sha256"] = "0" * 64
    swapped.after_hash = True

    def stage2_size(s, v, r):
        if s == 67215:
            v["customers"] = 50      # stage 1 and provenance are correct

    def missing_instance(out_dir):
        (out_dir / "v7" / "instance_67213.json").unlink()

    def extra_instance(out_dir):
        path = out_dir / "s1_20.json"
        data = json.loads(path.read_text())
        extra_record = copy.deepcopy(data["records"][0])
        extra_record.update(instance_seed=99999, customers=999)
        data["records"].append(extra_record)
        path.write_text(json.dumps(data))

    def unsupported_size(s, r, new):
        if s == 67200:
            r["customers"] = 999

    def wrong_expected_size(s, r, new):
        if s == 67200:
            r["customers"] = 50

    cases = {
        "extra seed with unsupported size": dict(extra=extra_instance),
        "prescribed seed unsupported size": dict(mutate_s1=unsupported_size),
        "prescribed seed wrong size": dict(mutate_s1=wrong_expected_size),
        "missing stage-2 instance": dict(extra=missing_instance),
        "candidate budget changed": dict(mutate_s2=budget),
        "fewer validation scenarios": dict(mutate_s2=scenarios),
        "swapped provenance": dict(mutate_s2=swapped),
        "wrong stage-2 validation seed": dict(mutate_s2=wrong_s2_seed),
        "configuration dropped": dict(mutate_s2=dropped),
        "duplicate stage-2 record": dict(extra=dup),
        "wrong stage-1 validation seed": dict(mutate_s1=wrong_s1_validation_seed),
        "missing sweep cell (0.20, 0.5)": dict(mutate_s2=missing_cell),
        "plan null but status ok": dict(mutate_s2=silently_null),
        "stage-1 software error": dict(mutate_s1=stage1_software_error),
        "stage-2 software error file": dict(extra=s2_error_file),
        "stage-2 size disagrees": dict(mutate_s2=stage2_size),
    }
    for name, kw in cases.items():
        code, out = run(*build(**kw))
        ok &= code == 1
        print(f"{'REJECT expected':34s} {name:28s}-> exit {code} | {out[:80]}")

    target = Path("code/study_v6.py")
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n# edited after freeze\n")
        code, out = run(*build())
    finally:
        target.write_bytes(original)
    ok &= code == 1
    print(f"{'REJECT expected':34s} {'code edited after freeze':28s}-> exit {code} | {out[:80]}")

    shutil.rmtree(TMP)
    print("ALL SAFEGUARDS BEHAVE AS SPECIFIED" if ok else "SAFEGUARD FAILURE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
