"""Write the two self-contained LaTeX uploads for IJSS: Operations & Logistics.

  submission/ijss/latex_anonymous/  review copy: no author, no named statements, anonymised .bib
  submission/ijss/latex_named/      copy with author details

Each folder holds manuscript.tex with every \\ifanonymous block resolved, the
tables, macros, figures and .bib it needs, flat (no sub-folders), and is
compiled once here to check that it builds on its own.

Usage (after code/ijss_tables.py and code/build_ijss.py):
  cd code && python3 package_ijss.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper_ijss" / "routing_model_ijss.tex"
OUT = ROOT / "submission" / "ijss"


def resolve(tex: str, anonymous: bool) -> str:
    tex = tex.replace("\\newif\\ifanonymous\n", "").replace("\\anonymousfalse\n", "")
    tex = re.sub(r"% the review copy.*\n", "", tex)
    tex = re.sub(r"\\ifdefined\\anonbuild.*\n", "", tex)
    tex = tex.replace("\\newcommand{\\refsfile}{ijss_refs}", "\\newcommand{\\refsfile}{%s}"
                      % ("ijss_refs_anon" if anonymous else "ijss_refs"))

    def pick(m):
        body = m.group(1)
        parts = re.split(r"\\else(?![A-Za-z])", body, maxsplit=1)
        yes, no = parts[0], (parts[1] if len(parts) > 1 else "")
        return yes if anonymous else no
    tex = re.sub(r"\\ifanonymous(?![A-Za-z])(.*?)\\fi(?![A-Za-z])", pick, tex, flags=re.S)
    assert "anonymous" not in tex.replace("ijss_refs_anon", ""), "unresolved conditional"
    tex = re.sub(r"\\input\{\.\./paper(?:_itor)?/", r"\\input{", tex)
    tex = re.sub(r"\{\.\./paper/(Fig[^}]*)\}", r"{\1}", tex)
    return tex


def needed(tex: str):
    files = set()
    for m in re.finditer(r"\\input\{([^}]*)\}", tex):
        f = m.group(1)
        files.add(f if f.endswith(".tex") else f + ".tex")
    for m in re.finditer(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", tex):
        files.add(m.group(1))
    return files


def locate(name: str) -> Path:
    for d in ("paper_ijss", "paper", "paper_itor"):
        p = ROOT / d / name
        if p.exists():
            return p
    raise FileNotFoundError(name)


def build(anonymous: bool) -> Path:
    d = OUT / ("latex_anonymous" if anonymous else "latex_named")
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    tex = resolve(SRC.read_text(), anonymous)
    (d / "manuscript.tex").write_text(tex)
    for f in sorted(needed(tex)):
        shutil.copy(locate(f), d / Path(f).name)
    # tables may \input further files
    for f in list(d.glob("tab_*.tex")):
        for g in needed(f.read_text()):
            shutil.copy(locate(g), d / Path(g).name)
    bib = "ijss_refs_anon.bib" if anonymous else "ijss_refs.bib"
    shutil.copy(ROOT / "paper_ijss" / bib, d / bib)
    run = lambda *c: subprocess.run(c, cwd=d, capture_output=True, text=True)  # noqa: E731
    run("pdflatex", "-interaction=nonstopmode", "manuscript.tex")
    run("bibtex", "manuscript")
    run("pdflatex", "-interaction=nonstopmode", "manuscript.tex")
    r = run("pdflatex", "-interaction=nonstopmode", "manuscript.tex")
    log = (d / "manuscript.log").read_text()
    assert (d / "manuscript.pdf").exists() and "undefined" not in log, f"build failed in {d}"
    assert "LaTeX Error" not in log and "not found" not in log, f"missing file in {d}"
    text = subprocess.run(["pdftotext", str(d / "manuscript.pdf"), "-"], capture_output=True, text=True).stdout
    if anonymous:
        for word in ("Suhan", "Lahore", "0009-0004", "syedsuhanali", "zenodo.23"):
            assert word not in text, f"identifying text in review copy: {word}"
    else:
        assert "Suhan Ali" in text and "zenodo.23185704" in text.replace("\n", "")
    for f in d.iterdir():
        if f.stem == "manuscript" and f.suffix in (".aux", ".bbl", ".blg", ".log", ".out", ".pdf"):
            f.unlink()
    return d


def main():
    for anon in (True, False):
        d = build(anon)
        print("ok", d.relative_to(ROOT), len(list(d.iterdir())), "files")


if __name__ == "__main__":
    main()
