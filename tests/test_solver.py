from ortools.sat.python import cp_model

from data import DataBundle
from model import build_model
from solver import solve_and_report, check_hard_violations


def test_solve_and_report_returns_feasible_with_zero_hard_violations():
    data = DataBundle.default()
    model, vars_dict = build_model(data)

    solver, status, vars_dict = solve_and_report(model, vars_dict, data, time_limit_s=40)

    assert status in (cp_model.FEASIBLE, cp_model.OPTIMAL)

    violations = check_hard_violations(
        solver, vars_dict['tv'], vars_dict['oe1'], vars_dict['oe2'],
        vars_dict['lv'], vars_dict['lr'], vars_dict['div_day_hours'], data,
    )
    assert violations == [], f"unexpected hard violations: {violations}"
