# Dynamic Dashboard + Individual Solver Comparison — Design

Date: 2026-08-10
Status: Approved by user, entering implementation

## 1. Motivation

The multi-objective timetable scheduler (`mutliobjective-timetable-scheduler-`) currently has:
- A single, bespoke CP-SAT formulation (`model.py`) built directly against hardcoded Python
  globals in `data.py` (divisions, batches, teachers, subjects, rooms, weights).
- A Pareto epsilon-constraint sweep (`pareto.py`) that produces a multi-objective front
  (faculty/student/resource score trade-offs), which is the project's standout feature and is
  being kept as-is in spirit.
- A FastAPI webapp (`webapp/server.py`) that solves the CP-SAT model **synchronously at server
  startup**, blocking the server from accepting any request until the ~90s solve finishes.
- No way to edit the input data without hand-editing `data.py` in code.
- No solvers other than CP-SAT.

The sibling project `timetable/` demonstrates a more mature pattern worth borrowing: dynamic
entity input via a dashboard, a DB as source of truth, on-demand background solving, and multiple
interchangeable solvers (Greedy/MIP/GA/CP-SAT) scored by one shared scoring module so they're
directly comparable.

This spec adds those capabilities to `mutliobjective-timetable-scheduler-` while preserving its
existing CP-SAT formulation and Pareto sweep, per explicit user direction to build this
**custom, against the existing `data.py`-shaped structure** rather than importing `timetable`'s
generic engine.

## 2. Pre-existing bug discovered during design (in scope to fix)

`model.py`'s student-score + resource-score + objective-assembly section (roughly lines 439–596)
is duplicated verbatim as lines 597–769. Net effects:
- `student_penalties` (ST2/ST3/ST4 terms) get appended twice, so `student_score` used by the
  live CP-SAT/Pareto objective is inflated versus the intended formula.
- The model carries ~2x the necessary auxiliary variables for that section, which is part of why
  a solve takes the full 90s budget.

`fix_model.py` is a leftover one-off migration script that attempted to fix this by
line-splicing `model.py`; it only partially worked (it deduplicated the "campus stay" ST1 block
but not the ST2/ST3/ST4/R1/R2/objective block) — the duplication above is still present in the
current file. `model_modified.py` is an abandoned, never-imported parallel attempt at a fix plus
an unrelated ST5 "campus stay" refinement.

**Decision:** `model.py` gets rewritten cleanly (single canonical copy of every section) as part
of the Phase 1 refactor below. `fix_model.py` and `model_modified.py` are dead weight and will be
deleted once the clean rewrite lands. `pareto_diagnostic.py` (a diagnostic script importing
`model.build_model()`) is updated to match the new `build_model(data)` signature but otherwise
left alone.

## 3. Decisions made (via clarifying questions)

1. **Architecture:** custom-built against the existing `data.py`/`model.py` shape — no import of
   `timetable`'s generic `ProblemInstance` engine. New Greedy/MIP/GA solvers target the same
   bespoke variable structure (`tv`, `oe1`/`oe2`, `lv`, `lr`) as the current CP-SAT model.
2. **Persistence:** a SQLite DB (SQLModel), mirroring `timetable`'s `platform.db` pattern.
   `data.py`'s current values become the seed dataset, loaded via `POST /api/seed` the first time
   the DB is empty.
3. **Dashboard flexibility:** full CRUD including counts — divisions, theory subjects, and lab
   subjects can be freely added/removed. Two batches per division stays a fixed domain rule
   (matches `timetable`'s own hard constraint 16). The two magic-index special cases
   (`WE_LAB_IDX` "twice-weekly", `CMPM_LAB_IDX` "sibling-sync") become per-lab-subject boolean
   flags instead of hardcoded indices. The 5-day/9-slot time grid stays fixed (not part of this
   request).
4. **Page layout:** new `/dashboard` page for data entry, alongside the existing results page
   (extended with a solver picker + "Compare all" button), mirroring `timetable`'s
   `/dashboard` + `/platform` split. The Pareto view stays where it is.

## 4. Data model

New SQLite DB, file `webapp/data/scheduler.db`, via SQLModel:

| Table | Fields |
|---|---|
| `Division` | id, name, classroom_name |
| `TheorySubject` | id, name, weekly_sessions, is_difficult |
| `TheorySubjectTeacher` | theory_subject_id, division_id, teacher_id |
| `LabSubject` | id, name, twice_weekly, sibling_sync, paired_theory_subject_id (nullable FK) |
| `LabSubjectTeacher` | lab_subject_id, division_id, batch_slot (0 or 1), teacher_id |
| `Teacher` | id, code, name |
| `LabRoom` | id, name |
| `Weights` | single row: all 11 penalty weights + `min_hours_per_day` / `max_hours_per_day` |

Batch identity is derived, not stored: batch `(division_id, batch_slot)` for `batch_slot in {0,1}`.
`BATCHES`/`DIV_TO_BATCHES`/`SIBLING_PAIRS`/`BATCH_TO_DIV` (currently hardcoded lists in `data.py`)
become computed properties of the loaded division set.

### `DataBundle`

`data.py` stops being a module of hardcoded globals and becomes a `DataBundle` dataclass with the
same fields `model.py`/`pareto.py`/`extract_schedule.py`/`solver.py` currently import as module
globals (`DAYS`, `NUM_DIVS`, `DIVISIONS`, `THEORY_SUBJ`, `LAB_SUBJ`, `ALL_TEACHERS`, weights,
etc.). Two constructors:
- `DataBundle.default()` — today's hardcoded values (used as the seed dataset and by existing
  tests/CLI scripts, so `main.py` keeps working unchanged).
- `DataBundle.from_db(session)` — builds the same shape from DB rows, deriving
  `THEORY_LAB_PAIRS` from each theory subject's linked lab subjects and deriving
  `twice_weekly`/`sibling_sync` index lists from the per-subject flags instead of
  `WE_LAB_IDX`/`CMPM_LAB_IDX`.

`build_model()` becomes `build_model(data: DataBundle)`; likewise `extract_schedule(solver,
vars_dict, data)`, `check_hard_violations(..., data)`, and the CLI/pareto entry points thread the
same `data` argument through. This is the one invasive, mechanical change touching every existing
file — everywhere `from data import X` currently happens, it becomes `data.X` on a passed-in
bundle.

## 5. `scoring.py` — shared comparison layer

New module, pure Python, no CP-SAT dependency. Takes a concrete **assignment** (plain Python
structure: which theory/lab sessions landed on which day/slot/room, which day has which break,
which days are OE1/OE2) and a `DataBundle`, and returns the same shape as today's
`check_hard_violations()` plus `faculty_score`/`student_score`/`resource_score`/`total_penalty`,
computed with the exact same formulas currently embedded in `model.py`'s CP-SAT constraints
(F1/F2/F3/F4/F5, ST2/ST3/ST4, R1/R2).

- CP-SAT's result is converted to this assignment shape via `solver.Value()` once, then scored by
  `scoring.py` — replacing the current `check_hard_violations()` special-cased to CP-SAT vars.
- Greedy/GA produce this assignment shape natively.
- MIP produces it via the CBC solver's `.Value()`/`.solution_value()` calls, same conversion
  pattern as CP-SAT.

This guarantees all four solvers' reported hard-violation counts and penalty scores are computed
by literally the same code, making the comparison table meaningful.

## 6. Three new solvers

All three target the same hard-constraint set as `model.py`'s CP-SAT formulation (weekly counts,
no double-booking, batch/sibling sync, break placement, OE pattern, daily-hour bounds, etc.).

- **Greedy** (`greedy.py`): constructive, no backtracking. Order: lab placement (tightest —
  batch-pairing, sibling-sync, shared room pool) → theory placement → OE day selection → break
  selection. First feasible slot/room per item, deterministic given a seed. Sub-second; used both
  standalone and as a GA seed.
- **MIP** (`mip_solver.py`, OR-Tools CBC via `pywraplp`): same hard constraints as CP-SAT,
  hand-linearized. The reified booleans CP-SAT builds natively (`AddBoolAnd`, `AddMaxEquality`,
  `OnlyEnforceIf`) become explicit linear indicator constraints — AND-of-k-booleans via
  `z >= sum(vi) - (k-1)`, MAX/OR-of-booleans via `z >= vi` (each i) + `z <= sum(vi)`. Every soft
  term in the current model is exactly linearizable this way (no term needs to be dropped, unlike
  `timetable`'s MIP which drops gap-minimization) — more verbose to write than CP-SAT's built-ins,
  but not an approximation.
- **GA** (`ga_solver.py`): hand-rolled. Gene groups: lab placement per batch-occurrence, theory
  placement per division-subject-occurrence, one global OE day-pair gene, break-slot gene per
  division/day. Staged constructive initialization (one individual seeded from the Greedy
  solution). Structured crossover per division/batch + repair pass (fix duplicate-slot
  assignments, re-sync siblings, re-validate weekly counts). Mutation reassigns one gene + repair.
  Fitness = `scoring.py`'s hard-violation count (dominant, large weight) plus
  faculty+student+resource sum. Params in the same range as `timetable`'s GA
  (`POP_SIZE`/`GENERATIONS`/`CROSSOVER_RATE`/`MUTATION_RATE`/`ELITISM`), tuned during
  implementation for acceptable runtime against this problem's size.

## 7. Solving moves off server-startup

`@app.on_event("startup")` no longer calls `build_model()`/`solve_and_report()`. Solving becomes
an explicit action:

- `POST /api/runs` — body `{solver: "greedy"|"mip"|"ga"|"cpsat", time_limit_s}`. Runs as a
  FastAPI `BackgroundTasks` job (queued → running → done/failed), same pattern as
  `timetable/webapp/jobs.py`. Returns a run id.
- `GET /api/runs/{id}` — poll status/result.
- `POST /api/compare` — body `{solvers: [...], time_limit_s}`. Runs each requested solver
  sequentially (avoids CP-SAT/MIP resource contention over shared cores) and returns one table:
  hard violations, faculty/student/resource/total penalty, wall-clock — one row per solver.
- `GET /api/readiness` — validates the DB has enough data to build a model (divisions with
  batches, at least one theory/lab subject with teachers assigned, etc.), same spirit as
  `timetable`'s readiness banner.

## 8. Dashboard (`/dashboard`)

Vanilla JS + FastAPI routers, no build step, no auth (matching this project's current scope) —
CRUD screens for Divisions, Theory Subjects (+ per-division teacher), Lab Subjects (+ per-batch
teacher, twice-weekly/sibling-sync checkboxes), Teachers, Rooms (classrooms + labs), and Weights.
`POST /api/seed` pre-populates it with `DataBundle.default()`'s values on first run so the
dashboard is never empty out of the box.

## 9. Results page + Compare UI

Existing `/` results page gains:
- A solver picker (Greedy / MIP / GA / CP-SAT) + time-budget input, calling `POST /api/runs`.
- A "Compare all" button calling `POST /api/compare`, rendering the results table described in
  §7, plus a per-solver grid tab (reusing the existing division-grid rendering already in
  `templates/index.html`/`static/styles.css`).
- A link to the existing Pareto front view (unchanged route).

## 10. Pareto sweep — dynamic epsilon bounds

`pareto.py`'s epsilon breakpoints (`e_stu=[250,220,210,200]`, `e_fac=[90,100,115,130]`) are
absolute numbers calibrated to the current hardcoded dataset; they'll silently stop making sense
against edited data (too loose = no discrimination, too tight = infeasible). Fix: `pareto.py`
first solves once with the plain `total_penalty` objective (already in `model.py`) to get a
baseline `(faculty_score, student_score, resource_score)`, then derives epsilon breakpoints as
percentages of that baseline (e.g. baseline × [1.5, 1.3, 1.15, 1.0]) instead of hardcoded
constants. `POST /api/pareto/generate` becomes a background job like the others (currently it's
a standalone script writing `webapp/pareto_solutions.json`); the existing `GET /api/pareto`
static-file read stays as a cache/fallback.

## 11. Non-goals

- No auth/multi-tenancy (not requested; matches this project's current scope).
- No editable time/slot grid (5 days × 9 slots stays fixed).
- No room-pool allocation for classrooms (stays 1 dedicated classroom per division).
- Not importing or depending on `timetable`'s codebase.

## 12. Delivery phases

1. DB + `DataBundle` + `model.py` refactor (bug fix + magic-index-to-flags) + dashboard CRUD +
   seed endpoint. CP-SAT/Pareto continue working, now dashboard-driven, solving moved off
   startup onto `POST /api/runs`.
2. `scoring.py` + Greedy solver.
3. MIP solver.
4. GA solver.
5. Compare UI wiring all four solvers together.
6. Pareto dynamic-epsilon-bounds fix.

Each phase is independently testable and useful on its own; later phases depend on earlier ones
(this is a sequential chain, not independent parallel work).
