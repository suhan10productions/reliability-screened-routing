"""Make the self-contained ITOR upload: one .tex (inputs, bibliography and SI
cross-references resolved), the class file and the figures.

Run after paper_itor/build.sh:
  cd code && python3 package_itor.py
Writes paper_itor/upload/ and paper_itor/upload.zip.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper_itor"
OUT = SRC / "upload"


def inline(text: str, base: Path) -> str:
    def rep(m):
        name = m.group(1)
        path = (base / name)
        if not path.suffix:
            path = path.with_suffix(".tex")
        return inline(path.read_text().rstrip("\n"), base)
    return re.sub(r"\\input\{([^}]*)\}", rep, text)


def main():
    tex = (SRC / "routing_model_itor.tex").read_text()
    labels = {}
    for line in (SRC / "si_labels.aux").read_text().splitlines():
        m = re.match(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", line)
        if m:
            labels[m.group(1)] = m.group(2)
    tex = re.sub(r"\\newcommand\{\\SI\}\[1\]\{[^\n]*\}\n", "", tex)
    used = set(re.findall(r"\\ref\{S-([^}]*)\}", tex)) | set(re.findall(r"\\SI\{([^}]*)\}", tex))
    for lab in used:
        assert lab in labels, lab
    tex = re.sub(r"\\SI\{([^}]*)\}", lambda m: f"Section~{labels[m.group(1)]}", tex)
    tex = re.sub(r"\\ref\{S-([^}]*)\}", lambda m: labels[m.group(1)], tex)
    tex = tex.replace("\\usepackage{xr-hyper}\n", "")
    tex = re.sub(r"\\externaldocument\[S-\]\{[^}]*\}\n", "", tex)
    tex = re.sub(r"\\newcommand\{\\SI\}\[1\]\{[^\n]*\}\n", "", tex)
    tex = inline(tex, SRC)
    # tables written by itor_tables.py may themselves point to the SI
    tex = re.sub(r"\\ref\{S-([^}]*)\}", lambda m: labels[m.group(1)], tex)
    bbl = (SRC / "routing_model_itor.bbl").read_text()
    tex = re.sub(r"\\bibliographystyle\{itor\}\n\\bibliography\{[^}]*\}", lambda m: bbl.rstrip("\n"), tex)
    tex = tex.replace("../paper/Fig1.pdf", "Fig1.pdf").replace("../paper/Fig2.pdf", "Fig2.pdf")
    assert "\\input{" not in tex and "\\ref{S-" not in tex and "../paper" not in tex, [m.group(0) for m in re.finditer(r".{20}(\\input\{|\\ref\{S-|\.\./paper).{20}", tex)]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "routing_model_itor.tex").write_text(tex)
    for f in ("itor.cls",):
        shutil.copy(SRC / f, OUT / f)
    for f in ("Fig1.pdf", "Fig2.pdf", "Fig1.eps", "Fig2.eps"):
        shutil.copy(ROOT / "paper" / f, OUT / f)
    with zipfile.ZipFile(SRC / "upload.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()):
            z.write(f, f.name)
    print("upload:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
