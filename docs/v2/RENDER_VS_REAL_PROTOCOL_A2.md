# Render-vs-real protocol — Amendment A2 (state-polynomial degree)

Written 16 Nov 2026 by session R4 **before any render-vs-real score is computed** (hash in `docs/v2/PREREGISTRATION.md`,
Entry 3). Changes one sentence of A1.2.

A1.2 fixed cubic polynomials for the per-line spacecraft position and attitude. Running the geometry stage on the dev sample,
one row (M162526179RC × site01_roi6) exceeded the A1.2 attitude-fit gate by 5 % (6.27 µrad vs 6.00 µrad = 0.1 binned pixel):
the cubic is slightly too stiff for that attitude history. **New rule:** the degree is the smallest of 3, 4, 5, 6, 7 whose fit
passes the unchanged A1.2 gate (≤ 1 m, ≤ 0.1 binned pixel), with max(41, 8 × (degree + 1)) Chebyshev–Lobatto nodes; the
degree is recorded per row (`fit_degree` in `results/geometry.csv`). A row that fails at degree 7 stays gated. The criterion is
the geometric fit residual against SPICE, never an image score.
