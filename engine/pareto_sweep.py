"""Generic AUGMECON2-style epsilon-constraint Pareto sweep, reusing the CP-SAT model's four named
objective categories (`engine.solvers.cpsat.OBJECTIVE_CATEGORIES`: rooms, labs, students, faculty)
via `CPSATSolver.solve_pareto_point()` -- no new solver, no new algorithm. Works against ANY
`ProblemInstance` (any branch/division/year), not just one hardcoded dataset.

Extracted as a pure, side-effect-free module (no CSV/matplotlib) so `webapp/routers/pareto.py` can
call `sweep()` directly from a background job. "rooms" is excluded from the default pairs by the
same reasoning as the original research script: on typical DJSCE-shaped instances it reaches its
own unconstrained minimum regardless of what else is optimized (very low soft-weight in
scoring.py), so it never trades off against anything.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from engine.models import ProblemInstance, Solution
from engine.scoring import score
from engine.solvers.cpsat import CPSATSolver

DEFAULT_TIME_LIMIT_S = 30
DEFAULT_SWEEP_POINTS = 5

DEFAULT_PAIRS: list[tuple[str, str]] = [
    ("faculty", "students"),
    ("faculty", "labs"),
    ("students", "labs"),
]


@dataclass
class FrontierPoint:
    pair: str
    epsilon: int
    bound_category: str
    minimize_category: str
    bound_value: int | None
    minimize_value: int | None
    hard_violations: int
    wall_s: float


def _payoff_table(solver: CPSATSolver, problem: ProblemInstance, bound_category: str,
                   minimize_category: str, time_limit_s: float,
                   warm_start: Solution | None) -> tuple[int, int]:
    _sol_bound, vals_bound = solver.solve_pareto_point(
        problem, bounds={}, minimize=bound_category, time_limit_s=time_limit_s, warm_start=warm_start)
    _sol_min, vals_min = solver.solve_pareto_point(
        problem, bounds={}, minimize=minimize_category, time_limit_s=time_limit_s, warm_start=warm_start)
    tight_end = vals_bound[bound_category]
    loose_end = vals_min[bound_category]
    if tight_end is None or loose_end is None:
        raise RuntimeError(
            f"payoff table solve was infeasible for pair ({bound_category}, {minimize_category})")
    return tight_end, loose_end


def _epsilon_grid(tight_end: int, loose_end: int, n: int) -> list[int]:
    if loose_end <= tight_end:
        return [tight_end]
    step = (loose_end - tight_end) / (n - 1)
    return sorted({round(tight_end + i * step) for i in range(n)})


def sweep_pair(solver: CPSATSolver, problem: ProblemInstance, bound_category: str,
               minimize_category: str, time_limit_s: float = DEFAULT_TIME_LIMIT_S,
               sweep_points: int = DEFAULT_SWEEP_POINTS,
               warm_start: Solution | None = None) -> list[FrontierPoint]:
    pair_label = f"{bound_category}<=eps,min={minimize_category}"
    tight_end, loose_end = _payoff_table(solver, problem, bound_category, minimize_category,
                                          time_limit_s, warm_start)
    grid = _epsilon_grid(tight_end, loose_end, sweep_points)

    points = []
    for epsilon in grid:
        t0 = time.time()
        sol, vals = solver.solve_pareto_point(
            problem, bounds={bound_category: epsilon}, minimize=minimize_category,
            time_limit_s=time_limit_s, warm_start=warm_start)
        wall = time.time() - t0
        hard = score(sol, problem).hard_violations if sol.assignments else -1
        points.append(FrontierPoint(
            pair=pair_label, epsilon=epsilon, bound_category=bound_category,
            minimize_category=minimize_category, bound_value=vals[bound_category],
            minimize_value=vals[minimize_category], hard_violations=hard, wall_s=wall,
        ))
    return points


def sweep(problem: ProblemInstance, pairs: list[tuple[str, str]] | None = None,
          time_limit_s: float = DEFAULT_TIME_LIMIT_S,
          sweep_points: int = DEFAULT_SWEEP_POINTS) -> dict[str, list[FrontierPoint]]:
    """Run the full sweep across `pairs` (default: DEFAULT_PAIRS) against `problem`. Returns
    {pair_label: [FrontierPoint, ...]}, skipping (not raising for) any pair whose payoff table
    solve is infeasible on this instance."""
    from engine.solvers.greedy import GreedySolver

    solver = CPSATSolver()
    warm_start = GreedySolver().solve(problem)

    results: dict[str, list[FrontierPoint]] = {}
    for bound_category, minimize_category in (pairs or DEFAULT_PAIRS):
        pair_label = f"{bound_category}<=eps,min={minimize_category}"
        try:
            results[pair_label] = sweep_pair(
                solver, problem, bound_category, minimize_category,
                time_limit_s=time_limit_s, sweep_points=sweep_points, warm_start=warm_start)
        except RuntimeError:
            results[pair_label] = []
    return results
