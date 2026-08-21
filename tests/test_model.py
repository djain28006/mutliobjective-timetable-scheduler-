from ortools.sat.python import cp_model

from data import DataBundle
from model import build_model


def test_build_model_validates_and_solves_feasible():
    data = DataBundle.default()
    model, vars_dict = build_model(data)

    assert model.Validate() == ''

    expected_keys = {
        'tv', 'lv', 'lr', 'oe1', 'oe2', 'is_break', 'div_day_hours',
        'faculty_score', 'student_score', 'resource_score', 'total_penalty',
    }
    assert expected_keys <= vars_dict.keys()

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 40
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    assert status in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    # Sanity bound: faculty/student/resource are independently-summed non-negative penalties
    # that must add up to total_penalty (this is exactly the bug being fixed — previously
    # duplicated ST2/ST3/ST4 terms made student_score inconsistent with this sum).
    fac = solver.Value(vars_dict['faculty_score'])
    stu = solver.Value(vars_dict['student_score'])
    res = solver.Value(vars_dict['resource_score'])
    tot = solver.Value(vars_dict['total_penalty'])
    assert fac >= 0 and stu >= 0 and res >= 0
    assert tot == fac + stu + res


def test_twice_weekly_lab_runs_exactly_twice():
    data = DataBundle.default()
    model, vars_dict = build_model(data)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 40
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    assert status in (cp_model.FEASIBLE, cp_model.OPTIMAL)

    lv = vars_dict['lv']
    we_lab_idx = next(i for i, s in enumerate(data.LAB_SUBJ) if s['name'] == 'WE-Lab')
    for b in range(data.NUM_BATCHES):
        count = sum(
            solver.Value(lv[(b, we_lab_idx, d, ss)])
            for d in range(data.NUM_DAYS) for ss in data.LAB_START_SLOTS
        )
        assert count == 2, f"batch {b} WE-Lab count == {count}, expected 2"
