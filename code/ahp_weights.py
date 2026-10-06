"""Reproduce the AHP weights used in the manuscript from their pairwise matrix.

Criteria order: distance cost, slack deficit, driver duration, fleet use.
Entry A[k][l] is the judged importance of criterion k relative to l on Saaty's
1-9 scale. Weights are the normalised principal eigenvector; the consistency
ratio uses Saaty's random index 0.90 for four criteria.

Provenance: the matrix was specified for an earlier criteria set in which the
third criterion was total distance. Its third row and column were not
re-elicited when that criterion became driver duration.
"""
import json

import numpy as np

A = np.array([
    [1,   3,   5,   7],
    [1/3, 1,   3,   5],
    [1/5, 1/3, 1,   2],
    [1/7, 1/5, 1/2, 1],
])
RANDOM_INDEX_N4 = 0.90
USED = (0.5693, 0.2643, 0.1055, 0.0609)   # weights in relscreen_v6.py and the paper


def main():
    vals, vecs = np.linalg.eig(A)
    k = int(np.argmax(vals.real))
    lam = float(vals.real[k])
    w = np.abs(vecs[:, k].real)
    w = w / w.sum()
    ci = (lam - 4) / 3
    cr = ci / RANDOM_INDEX_N4
    out = {"lambda_max": round(lam, 4), "weights": [round(float(x), 4) for x in w],
           "consistency_index": round(ci, 4), "consistency_ratio": round(cr, 4),
           "matches_weights_used": all(round(float(x), 4) == u for x, u in zip(w, USED))}
    print(json.dumps(out, indent=2))
    if not out["matches_weights_used"]:
        raise SystemExit("computed weights do not match the weights used in the study")


if __name__ == "__main__":
    main()
