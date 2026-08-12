"""
main.py — Entry point for the University Timetable Scheduling System.

Usage:
    python main.py

Requires:
    pip install ortools
"""

from data import DataBundle
from model import build_model
from solver import solve_and_report


def main():
    print("=" * 60)
    print("  University Timetable Scheduling System")
    print("  CP-SAT Solver  |  Google OR-Tools")
    print("=" * 60)

    data = DataBundle.default()

    print("\n[1/2] Building CP-SAT model …")
    model, vars_dict = build_model(data)

    # Validate model structure before solving
    err = model.Validate()
    if err:
        print(f"\n  [!] Model validation error:\n  {err}")
        return

    print("      Model built and validated successfully.")
    print("\n[2/2] Launching solver …\n")
    solve_and_report(model, vars_dict, data)


if __name__ == '__main__':
    main()
