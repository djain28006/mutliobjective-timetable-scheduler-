import sys, io, time
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model
from data import DataBundle
from model import build_model

def generate_pareto_front(time_limit=30):
    data = DataBundle.default()
    solutions = []
    seen = set()
    
    print("============================================================")
    print("  PARETO FRONT GENERATION (3D Rotating Epsilon-Constraint)")
    print("============================================================")
    print(f"{'Run Type':<15} | {'Fac':<5} | {'Stu':<5} | {'Res':<5} | {'Tot':<5} | {'Time(s)':<8} | {'Status'}")
    print("-" * 70)
    
    runs = []
    # Set 1: minimize faculty, bound student
    for e_stu in [250, 220, 210, 200]:
        runs.append(('Min Fac', e_stu, None))
    # Set 2: minimize student, bound faculty
    for e_fac in [90, 100, 115, 130]:
        runs.append(('Min Stu', None, e_fac))
    # Set 3: minimize resource, bound both
    for e_fac in [100, 115, 130]:
        runs.append(('Min Res', 220, e_fac))
        
    for run_type, e_stu, e_fac in runs:
        model, vars_dict = build_model(data)
        
        # Apply epsilon bounds based on run type
        run_desc = run_type
        if run_type == 'Min Fac':
            model.Add(vars_dict['student_score'] <= e_stu)
            model.Minimize(vars_dict['faculty_score'])
            run_desc = f"Min Fac (S<={e_stu})"
        elif run_type == 'Min Stu':
            model.Add(vars_dict['faculty_score'] <= e_fac)
            model.Minimize(vars_dict['student_score'])
            run_desc = f"Min Stu (F<={e_fac})"
        elif run_type == 'Min Res':
            model.Add(vars_dict['faculty_score'] <= e_fac)
            model.Add(vars_dict['student_score'] <= e_stu)
            model.Minimize(vars_dict['resource_score'])
            run_desc = f"Min Res (F<={e_fac})"
            
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 8
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.log_search_progress = False
        
        start = time.time()
        status = solver.Solve(model)
        wall_time = time.time() - start
        status_name = solver.StatusName(status)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            fac = solver.Value(vars_dict['faculty_score'])
            stu = solver.Value(vars_dict['student_score'])
            res = solver.Value(vars_dict['resource_score'])
            tot = fac + stu + res
            
            sig = (fac, stu, res)
            if sig not in seen:
                seen.add(sig)
                
                from extract_schedule import extract_schedule
                timetable_data = extract_schedule(solver, vars_dict, data)
                
                solution = {
                    "id": len(solutions) + 1,
                    "faculty_score": fac,
                    "student_score": stu,
                    "resource_score": res,
                    "total_penalty": tot,
                    "time": wall_time,
                    "status": status_name,
                    "timetable_data": timetable_data
                }
                solutions.append(solution)
                print(f"{run_desc:<15} | {fac:<5} | {stu:<5} | {res:<5} | {tot:<5} | {wall_time:<8.2f} | {status_name}")
            else:
                print(f"{run_desc:<15} | {fac:<5} | {stu:<5} | {res:<5} | {tot:<5} | {wall_time:<8.2f} | {status_name} (Duplicate)")
        else:
            print(f"{run_desc:<15} | ---   | ---   | ---   | ---   | {wall_time:<8.2f} | {status_name}")
                
    print("============================================================")
    print(f"  Found {len(solutions)} unique Pareto-optimal solutions.")
    
    # Save solutions for server
    import json
    with open("webapp/pareto_solutions.json", "w") as f:
        json.dump(solutions, f, indent=4)

if __name__ == '__main__':
    generate_pareto_front()
