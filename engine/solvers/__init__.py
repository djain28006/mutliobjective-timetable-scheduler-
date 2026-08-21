"""Solver registry — the single source of truth mapping a solver name to its class.

Both `cli.py` and the web platform import `SOLVERS` from here instead of each maintaining
their own dict (design.md §9 de-duplication). `pipeline`/`ensemble` are orchestration
*functions* in `timetable.pipeline` (they combine several of these solvers), so they are not
entries in this registry — callers dispatch them separately.
"""
from __future__ import annotations

from engine.solvers.base import SolverBase
from engine.solvers.greedy import GreedySolver
from engine.solvers.mip import MIPSolver
from engine.solvers.ga import GASolver
from engine.solvers.cpsat import CPSATSolver

# name -> solver class. Order is the canonical presentation order (fast -> exact).
SOLVERS: dict[str, type[SolverBase]] = {
    "greedy": GreedySolver,
    "mip": MIPSolver,
    "ga": GASolver,
    "cpsat": CPSATSolver,
}

__all__ = [
    "SOLVERS",
    "SolverBase",
    "GreedySolver",
    "MIPSolver",
    "GASolver",
    "CPSATSolver",
]
