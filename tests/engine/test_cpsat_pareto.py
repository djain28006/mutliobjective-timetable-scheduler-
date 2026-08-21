"""Tests for the CP-SAT objective-category split and the epsilon-constraint sweep support
(design.md Sec 15.3 / research/pareto_sweep.py). Time limits kept small per the project
convention (tests/test_solvers.py's docstring) so the suite runs quickly."""
import pytest

from engine.scoring import score
from engine.solvers.cpsat import OBJECTIVE_CATEGORIES, CPSATSolver


def test_solve_default_still_zero_hard_violations(small_problem):
    """The category-split refactor must not change solve()'s existing contract."""
    sol = CPSATSolver().solve(small_problem, time_limit_s=30)
    assert sol.status in ("OPTIMAL", "FEASIBLE")
    result = score(sol, small_problem)
    assert result.hard_violations == 0


def test_solve_pareto_point_respects_generous_bound(small_problem):
    sol, values = CPSATSolver().solve_pareto_point(
        small_problem, bounds={"faculty": 10_000}, minimize="students", time_limit_s=25)
    assert sol.status in ("OPTIMAL", "FEASIBLE")
    assert set(values) == set(OBJECTIVE_CATEGORIES)
    assert values["faculty"] is not None
    assert values["faculty"] <= 10_000
    assert score(sol, small_problem).hard_violations == 0


def test_solve_pareto_point_tight_bound_never_raises(small_problem):
    """A very tight bound may make the instance harder or infeasible for this category, but the
    solver must never raise (matches CLAUDE.md's "solvers never raise on infeasible" rule)."""
    sol, values = CPSATSolver().solve_pareto_point(
        small_problem, bounds={"faculty": 0}, minimize="students", time_limit_s=25)
    assert sol.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "TIMEOUT")
    if sol.status in ("OPTIMAL", "FEASIBLE"):
        assert values["faculty"] is not None
        assert values["faculty"] <= 0
    else:
        assert all(v is None for v in values.values())


def test_solve_pareto_point_unknown_category_raises(small_problem):
    with pytest.raises(ValueError):
        CPSATSolver().solve_pareto_point(small_problem, bounds={"bogus": 1}, minimize="rooms", time_limit_s=5)
    with pytest.raises(ValueError):
        CPSATSolver().solve_pareto_point(small_problem, bounds={}, minimize="bogus", time_limit_s=5)
