import sys, io, time
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model
from model import build_model

def run_diagnostic():
    print("============================================================")
    print("  DIAGNOSTIC RUN: Epsilon-Constraint Bounds Test")
    print("============================================================")
    
    # Set 1: Minimize Faculty, bound Student <= 250
    model1, vars1 = build_model()
    model1.Add(vars1['student_score'] <= 250)
    model1.Minimize(vars1['faculty_score'])
    solver1 = cp_model.CpSolver()
    solver1.parameters.max_time_in_seconds = 30
    print("Running Set 1 (Min Fac, Stu <= 250)...")
    status1 = solver1.Solve(model1)
    if status1 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Set 1: {solver1.StatusName(status1)} -> Fac: {solver1.Value(vars1['faculty_score'])}, Stu: {solver1.Value(vars1['student_score'])}, Res: {solver1.Value(vars1['resource_score'])}")
    else:
        print(f"Set 1: INFEASIBLE")

    # Set 2: Minimize Student, bound Faculty <= 130
    model2, vars2 = build_model()
    model2.Add(vars2['faculty_score'] <= 130)
    model2.Minimize(vars2['student_score'])
    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = 30
    print("Running Set 2 (Min Stu, Fac <= 130)...")
    status2 = solver2.Solve(model2)
    if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Set 2: {solver2.StatusName(status2)} -> Fac: {solver2.Value(vars2['faculty_score'])}, Stu: {solver2.Value(vars2['student_score'])}, Res: {solver2.Value(vars2['resource_score'])}")
    else:
        print(f"Set 2: INFEASIBLE")

    # Set 3: Minimize Resource, bound Faculty <= 130, Student <= 220
    model3, vars3 = build_model()
    model3.Add(vars3['faculty_score'] <= 130)
    model3.Add(vars3['student_score'] <= 220)
    model3.Minimize(vars3['resource_score'])
    solver3 = cp_model.CpSolver()
    solver3.parameters.max_time_in_seconds = 30
    print("Running Set 3 (Min Res, Fac <= 130, Stu <= 220)...")
    status3 = solver3.Solve(model3)
    if status3 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Set 3: {solver3.StatusName(status3)} -> Fac: {solver3.Value(vars3['faculty_score'])}, Stu: {solver3.Value(vars3['student_score'])}, Res: {solver3.Value(vars3['resource_score'])}")
    else:
        print(f"Set 3: INFEASIBLE")

if __name__ == '__main__':
    run_diagnostic()
