# Solver tooling for the model and the schedule

Question (requirements 1.1 and 1.2): which tools should (a) fit the house model's parameters to recorded data and (b) optimise the heat pump's schedule (when it runs, at which setpoint) over 24–48 h, re-planned every 15–60 min, unattended on the Debian mini PC from the turn of the year 2026/2027? The model must reproduce closely what actually happens, and a model- and optimiser-based approach is a goal in itself.

Provenance: research by a sub-agent on 2026-11-22. Versions, licences, wheel tags and dependencies were read from the PyPI JSON API (`https://pypi.org/pypi/<name>/json`) that day. Unpacked sizes were measured from the downloaded x86_64 wheels. Feature claims come from each project's README, docs or source, linked below. The sections "Handling the on/off decision" and "Recommendation" are the sub-agent's analysis, not taken from a source. Not reviewed by a person.

## Candidates

Both services run on `python:3.15-slim-trixie` and currently install no numerical packages, so every package below would be a new dependency.

| Stack | Current release | Licence | x86_64 wheel for Python 3.15 | Size |
|---|---|---|---|---|
| JAX (jax + jaxlib) | 0.12.1, 2026-11-18 | Apache-2.0 | yes | jaxlib wheel 83 MB, 318 MB unpacked |
| diffrax | 0.7.2, 2026-02-18 | Apache-2.0 | pure Python | 0.2 MB |
| optimistix | 0.1.0, 2026-02-16 | Apache-2.0 | pure Python | 0.1 MB |
| optax | 0.2.9, 2026-11-11 | Apache-2.0 | pure Python | 0.4 MB |
| jaxopt | 0.8.5, 2025-04-14 | Apache-2.0 | pure Python | unmaintained |
| CasADi | 3.8.2, 2026-10-27 | LGPL-3.0 | yes (abi3 wheel, cp311 and later) | 92 MB wheel, 281 MB unpacked |
| do-mpc | 5.1.2, 2026-09-03 | LGPL-3.0 | pure Python | needs casadi, matplotlib, pandas |
| cvxpy | 1.9.3, 2026-09-19 | Apache-2.0 | **no** (wheels up to cp314); dependency osqp also stops at cp314 | 4.5 MB plus solvers |
| SciPy | 1.18.1, 2026-08-21 | BSD-3-Clause | yes | 35 MB wheel |

- **JAX, diffrax, optimistix.** JAX provides CPU-only pip wheels for Linux x86_64 (https://github.com/jax-ml/jax/blob/main/docs/installation.md). Diffrax offers ODE solvers, including implicit ones, with "multiple adjoint methods for backpropagation" (https://github.com/patrick-kidger/diffrax). Optimistix covers "root finding, minimisation, fixed points, and least squares" (https://github.com/patrick-kidger/optimistix). Diffrax 0.7.2 depends on optimistix, equinox, lineax, jaxtyping and wadler-lindig (PyPI metadata). Neither library has integer variables or constraints. Soft constraints are penalty terms in the loss, and on/off decisions have to be handled by the user (see below). Last commits: diffrax 2026-09-06, optimistix 2026-08-11 (GitHub API).
- **jaxopt.** Its README says: "JAXopt is no longer maintained nor developed". Some features were ported to optax (https://github.com/google/jaxopt). Do not use it.
- **CasADi.** Symbolic modelling with automatic differentiation, including exact Hessians, plus integrators and NLP solvers. The 3.8.2 x86_64 wheel bundles the `ipopt` and `bonmin` (MINLP) plugins and the `highs`, `cbc` and `osqp` QP/LP plugins (counted in the wheel's file list). `nlpsol` has a `discrete` option that "Indicates which of the variables are discrete, i.e. integer-valued" (https://github.com/casadi/casadi/blob/main/casadi/core/nlpsol.cpp). Hard constraints are native. Soft constraints are slack variables with a penalty. LGPL is compatible with an MIT project that only imports it, but it is not MIT.
- **do-mpc.** An MPC and moving-horizon-estimation layer on CasADi. It adds matplotlib and pandas (PyPI metadata). Last commit 2026-09-22.
- **cvxpy.** Requires the problem to be convex (DCP, https://www.cvxpy.org/tutorial/dcp/index.html). `boolean=True` and `integer=True` variables give mixed-integer problems (https://github.com/cvxpy/cvxpy/blob/master/doc/source/tutorial/constraints/index.rst). highspy (HiGHS) is a required dependency of 1.9.3 (PyPI metadata). The master docs also describe "Disciplined Nonlinear Programming" with `prob.solve(nlp=True)` and IPOPT "recommended", and warn that an NLP solver "may converge to an infeasible point" (https://github.com/cvxpy/cvxpy/blob/master/doc/source/tutorial/dnlp/index.rst). Constraint: a COP that depends on supply and outdoor temperature times the heat output is not convex. EMHASS works around this with linearisation and dynamic programming (requirements 1.2).
- **SciPy.** `scipy.integrate` (solve_ivp) and `scipy.optimize` (least_squares, minimize). Gradients come from finite differences or are coded by hand. `scipy.optimize.milp` "is a wrapper of the HiGHS linear optimization software" (https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html). SciPy is already a dependency of JAX.

## Handling the on/off decision

- **Combinatorial integral approximation.** Solve the relaxed problem, with an on-fraction between 0 and 1 per time step. Then round to on/off with a bounded error, and re-solve the continuous variables with the switching fixed. The bound and the method: Sager, Bock & Diehl, "The integer approximation error in mixed-integer optimal control", Math. Program. 133:1–23, doi:10.1007/s10107-010-0405-3 (checked against Crossref). Minimum up and down times fit into the rounding step, as in pycombina: Bürger et al. 2020, IFAC-PapersOnLine, doi:10.1016/j.ifacol.2020.12.1799 (Crossref only, text not read; pycombina is not on PyPI).
- **Penalty and smoothing.** Use a sigmoid of a continuous control as "on", and add penalties for fractional values and for each start. This works with any gradient optimiser, but it is non-convex, and the result depends on the starting point and on how fast the penalty weight rises.
- **Hybrid.** Enumerate a small set of on-blocks (start time × duration, respecting the minimum run time). For each, solve the setpoints with a gradient method, `vmap`-ed over the candidates in JAX, and keep the cheapest. The search is exhaustive over the set, so the plan is reproducible. The cost grows with the number of blocks.

## Recommendation for the first prototype

Build the model once in JAX, with diffrax and optimistix:
1. Fit the parameters with optimistix least squares (Levenberg–Marquardt) through diffrax solves of the recorded Home Assistant data.
2. Use the same model and loss for the schedule, with the hybrid scheme above: a small enumeration of heat-pump on-blocks, and gradient optimisation of the setpoints inside each block.

Arguments for it:
- one differentiable model serves both fitting and planning;
- soft penalties are expressed directly as the principal's loss functions (1.1);
- the principal already knows the stack;
- all parts are Apache-2.0 and have Python 3.15 wheels.

Strongest argument against: CasADi with IPOPT is the established tool for exactly this kind of nonlinear MPC. It has hard constraints, exact Hessians, an MINLP solver (Bonmin) and an MPC layer (do-mpc), all in one LGPL wheel. A penalty-based gradient method run unattended can return a poor local optimum or a plan that violates a limit, and nothing reports it. Two mitigations: check every plan against hard limits before it is sent, and fall back to the heat pump's own heating curve when the check fails. A further cost: JAX adds about 320 MB, and it recompiles when array shapes change, so the horizon length and the step must stay fixed.

New dependencies for the recommendation: jax, jaxlib, diffrax, optimistix, equinox, lineax, jaxtyping, wadler-lindig, ml_dtypes, opt_einsum, numpy, scipy (and optax if a first-order optimiser is wanted). The CasADi alternative needs casadi (and numpy), plus do-mpc, matplotlib and pandas if do-mpc is used.

## Not verified

- Run times and memory on the mini PC. Nothing was benchmarked, and the mini PC's CPU model is not recorded here.
- Whether the cvxpy DNLP feature in the master docs is in release 1.9.3, and whether cvxpy builds from source on Python 3.15.
- Whether Bonmin in the CasADi wheel is practical for a 48 h horizon with a minimum run time.
- The text of the pycombina paper (only the Crossref record was read).
