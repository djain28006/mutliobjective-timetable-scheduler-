import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import copy

from data import DataBundle
from model import build_model
from solver import solve_and_report, check_hard_violations
from ortools.sat.python import cp_model

app = FastAPI()

# Global state to store the schedule
schedule_data = {
    "divisions": [],
    "teachers": {},
    "classrooms": {},
    "labs": {},
    "stats": {}
}

@app.on_event("startup")
def run_solver():
    global schedule_data
    print("Running solver before starting web server...")
    data = DataBundle.default()
    model, vars_dict = build_model(data)
    solver, status, _ = solve_and_report(model, vars_dict, data)

    status_name = solver.StatusName(status)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        print("Solver failed to find a solution.")
        schedule_data["stats"] = {"status": status_name, "error": "No solution"}
        return

    tv = vars_dict['tv']
    oe1 = vars_dict['oe1']
    oe2 = vars_dict['oe2']
    lv = vars_dict['lv']
    lr = vars_dict['lr']
    div_day_hours = vars_dict['div_day_hours']

    violations = check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours, data)

    schedule_data["stats"] = {
        "status": status_name,
        "wall_time": round(solver.WallTime(), 2),
        "penalty": int(solver.ObjectiveValue()),
        "hard_violations": len(violations)
    }

    oe1_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe1[d])), None)
    oe2_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe2[d])), None)

    from extract_schedule import extract_schedule
    extracted = extract_schedule(solver, vars_dict, data)
    
    schedule_data["divisions"] = extracted["divisions"]
    schedule_data["teachers"] = extracted["teachers"]
    schedule_data["classrooms"] = extracted["classrooms"]
    schedule_data["labs"] = extracted["labs"]
    
    print("Solver data extracted and ready!")


@app.get("/api/timetable/divisions")
def get_divisions():
    return schedule_data["divisions"]

@app.get("/api/timetable/teachers")
def get_teachers():
    return schedule_data["teachers"]

@app.get("/api/timetable/classrooms")
def get_classrooms():
    return schedule_data["classrooms"]

@app.get("/api/timetable/labs")
def get_labs():
    return schedule_data["labs"]

@app.get("/api/stats")
def get_stats():
    return schedule_data["stats"]

@app.get("/api/pareto")
def get_pareto():
    import json
    import os
    file_path = os.path.join(os.path.dirname(__file__), "pareto_solutions.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []

app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("webapp/templates/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8750, reload=True)
