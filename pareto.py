import sys, io, time
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model
from model import build_model

def generate_pareto_front(max_solutions=8, time_limit=45):
    solutions = []
    seen = set()
    
def generate_pareto_front(time_limit=30):
    solutions = []
    seen = set()
    
    print("============================================================")
    print("  PARETO FRONT GENERATION (Weighted Sum Method)")
    print("============================================================")
    print(f"{'Weight':<10} | {'Fac':<5} | {'Stu':<5} | {'Res':<5} | {'Tot':<5} | {'Time(s)':<8} | {'Status'}")
    print("-" * 65)
    
    weights = [
        (100, 1),
        (10, 1),
        (3, 1),
        (1, 1),
        (1, 3),
        (1, 10),
        (1, 100)
    ]
    
    for w_fac, w_stu in weights:
        model, vars_dict = build_model()
        
        # Weighted objective
        model.Minimize(w_fac * vars_dict['faculty_score'] + w_stu * vars_dict['student_score'])
        
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
            tot = fac + stu
            
            sig = (fac, stu)
            if sig not in seen:
                seen.add(sig)
                
                from extract_schedule import extract_schedule
                timetable_data = extract_schedule(solver, vars_dict)
                
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
                weight_str = f"{w_fac}:{w_stu}"
                print(f"{weight_str:<10} | {fac:<5} | {stu:<5} | {res:<5} | {tot:<5} | {wall_time:<8.2f} | {status_name}")
            else:
                weight_str = f"{w_fac}:{w_stu}"
                print(f"{weight_str:<10} | {fac:<5} | {stu:<5} | {res:<5} | {tot:<5} | {wall_time:<8.2f} | {status_name} (Duplicate)")
        else:
            weight_str = f"{w_fac}:{w_stu}"
            print(f"{weight_str:<10} | ---   | ---   | ---   | ---   | {wall_time:<8.2f} | {status_name}")
                
    print("============================================================")
    print(f"  Found {len(solutions)} Pareto-optimal solutions.")
    
    # Save solutions for server
    import json
    with open("webapp/pareto_solutions.json", "w") as f:
        json.dump(solutions, f, indent=4)


if __name__ == '__main__':
    generate_pareto_front()
