from ortools.sat.python import cp_model

from data import DataBundle
from model import build_model
from solver import solve_and_report
from extract_schedule import extract_schedule


def test_extract_schedule_covers_every_division_and_slot():
    data = DataBundle.default()
    model, vars_dict = build_model(data)
    solver, status, vars_dict = solve_and_report(model, vars_dict, data, time_limit_s=40)
    assert status in (cp_model.FEASIBLE, cp_model.OPTIMAL)

    result = extract_schedule(solver, vars_dict, data)

    assert set(result.keys()) == {'divisions', 'teachers', 'classrooms', 'labs'}
    assert len(result['divisions']) == data.NUM_DIVS
    for div_info in result['divisions']:
        assert div_info['name'] in data.DIVISIONS
        assert div_info['classroom'] in data.CLASSROOMS
        # every (day, slot) cell is present exactly once
        assert len(div_info['timetable']) == data.NUM_DAYS * data.NUM_SLOTS

    for teacher in data.ALL_TEACHERS:
        assert teacher in result['teachers']
    for room in data.CLASSROOMS:
        assert room in result['classrooms']
    for room in data.LABS_LIST:
        assert room in result['labs']
