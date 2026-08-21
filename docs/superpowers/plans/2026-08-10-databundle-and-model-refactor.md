# DataBundle + model.py Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `data.py`'s hardcoded module-level globals with a `DataBundle` dataclass that
every existing entry point (`main.py`, `model.py`, `solver.py`, `extract_schedule.py`,
`pareto.py`, `pareto_diagnostic.py`) takes as an explicit parameter, fix the constraint-duplication
bug in `model.py`, and generalize the `WE_LAB_IDX`/`CMPM_LAB_IDX`/`CMPM_THEORY_IDX` magic indices
into per-subject boolean flags — all with zero behavior change except the bug fix.

**Architecture:** `data.py` becomes a single `DataBundle` dataclass with a `default()` factory
holding today's exact hardcoded values (as plain dicts inside `THEORY_SUBJ`/`LAB_SUBJ` lists, same
shape as before, just with new flag keys). Every function that currently does
`from data import X` is changed to receive a `data: DataBundle` argument and read `data.X`
instead. This is sub-phase 1a of the larger design in
`docs/superpowers/specs/2026-08-10-dynamic-dashboard-and-solvers-design.md` — it deliberately does
**not** touch the database, dashboard, or webapp yet (those are follow-up plans); it only makes the
existing CLI/solver code parameterizable so the DB-backed loader (`DataBundle.from_db()`) can be
added later without touching `model.py`/`solver.py` again.

**Tech Stack:** Python 3.11, OR-Tools CP-SAT (`ortools`, already installed), `pytest` (already
installed — verify with `python -m pytest --version`).

## Global Constraints

- No new third-party dependencies in this plan (SQLModel/FastAPI DB work is a separate follow-up
  plan).
- The **only** intended behavior change versus current `main.py` output is the duplication bug fix
  (student_score will report a lower, correct value; hard_violations count is unaffected). Every
  other constraint, weight, and default value must be preserved exactly.
- Tests that run a real CP-SAT solve use `time_limit_s=40` (not the production default of 90) to
  keep the suite reasonably fast while reliably reaching a FEASIBLE status (presolve alone takes
  ~10s on this model; first feasible solutions have appeared between 13s–18s in prior runs).
- Windows dev machine; run Python via `python` (not `python3`) and use Git Bash (`Bash` tool) or
  PowerShell for commands — this plan uses `Bash` tool syntax.
- Work happens directly in `v:/Projects/IPD/mutliobjective-timetable-scheduler-` (already a git
  repo on branch `main`, no uncommitted changes as of this plan).

---

### Task 1: `data.py` → `DataBundle` dataclass

**Files:**
- Modify: `data.py` (full rewrite)
- Test: `tests/test_data_bundle.py`

**Interfaces:**
- Produces: `DataBundle` dataclass with fields listed below, `DataBundle.default() -> DataBundle`
  (staticmethod/classmethod). All later tasks import `from data import DataBundle`.
- `THEORY_SUBJ` entries are dicts: `{'name': str, 'weekly': int, 'day_edges_only': bool,
  'teachers': {div_idx: code}}`.
- `LAB_SUBJ` entries are dicts: `{'name': str, 'twice': bool, 'sibling_sync': bool,
  'day_edges_only': bool, 'teachers': {batch_idx: code}}` (`sibling_sync` replaces the old
  `is_cmpm_lab` key name; `day_edges_only` is new — see Task 2 discovery below).

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty file) and `tests/test_data_bundle.py`:

```python
from data import DataBundle


def test_default_matches_original_shape():
    d = DataBundle.default()

    assert d.DAYS == ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    assert d.NUM_DAYS == 5
    assert d.SLOT_NAMES == ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9']
    assert d.NUM_SLOTS == 9
    assert d.ACADEMIC_SLOTS == list(range(9))
    assert d.LAB_START_SLOTS == list(range(8))
    assert d.LAST_SLOT == 8

    assert d.DIVISIONS == ['D1', 'D2', 'D3']
    assert d.NUM_DIVS == 3
    assert d.BATCHES == ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']
    assert d.NUM_BATCHES == 6
    assert d.BATCH_TO_DIV == [0, 0, 1, 1, 2, 2]
    assert d.DIV_TO_BATCHES == [[0, 1], [2, 3], [4, 5]]
    assert d.SIBLING_PAIRS == [(0, 1), (2, 3), (4, 5)]

    assert d.CLASSROOMS == ['Class-D1', 'Class-D2', 'Class-D3']
    assert d.NUM_CLASSROOMS == 3
    assert d.LABS_LIST == ['Lab-1', 'Lab-2', 'Lab-3', 'Lab-4']
    assert d.NUM_LABS == 4

    assert d.NUM_THEORY_SUBJ == 5
    assert [s['name'] for s in d.THEORY_SUBJ] == ['DS', 'ML-I', 'SDS', 'EFM', 'CMPM']
    assert d.THEORY_SUBJ[0]['weekly'] == 4
    assert d.THEORY_SUBJ[0]['teachers'] == {0: 'NM', 1: 'RP', 2: 'SAM'}
    # CMPM is the only theory subject with the day-edges-only placement rule
    assert [s['day_edges_only'] for s in d.THEORY_SUBJ] == [False, False, False, False, True]

    assert d.NUM_LAB_SUBJ == 6
    names = [s['name'] for s in d.LAB_SUBJ]
    assert names == ['DS-Lab', 'ML-Lab', 'SDS-Lab', 'WE-Lab', 'PBC-Lab', 'CMPM-Lab']
    # WE-Lab (idx 3) is the only twice-weekly lab
    assert [s['twice'] for s in d.LAB_SUBJ] == [False, False, False, True, False, False]
    # CMPM-Lab (idx 5) is the only sibling-sync + day-edges-only lab
    assert [s['sibling_sync'] for s in d.LAB_SUBJ] == [False, False, False, False, False, True]
    assert [s['day_edges_only'] for s in d.LAB_SUBJ] == [False, False, False, False, False, True]
    assert d.LAB_SUBJ[5]['teachers'] == {0: 'AVG', 1: 'MAA', 2: 'MAA', 3: 'AVG', 4: 'RP', 5: 'AVG'}

    assert d.ALL_TEACHERS == sorted({
        t for s in d.THEORY_SUBJ for t in s['teachers'].values()
    } | {
        t for s in d.LAB_SUBJ for t in s['teachers'].values()
    })
    assert d.THEORY_LAB_PAIRS == [(0, 0), (1, 1), (2, 2), (4, 5)]

    assert d.MIN_HOURS_PER_DAY == 5
    assert d.MAX_HOURS_PER_DAY == 8
    assert d.DIFFICULT_SUBJ_IDX == {0, 1, 4}

    assert d.W_FAC_GAP == 8
    assert d.W_FAC_OVERLOAD == 5
    assert d.W_FAC_H1 == 5
    assert d.W_FAC_H9 == 5
    assert d.W_FAC_CONSEC == 10
    assert d.W_STU_CONSEC_DIFF == 10
    assert d.W_STU_THEORY_H9 == 5
    assert d.W_STU_3DAYS_SAME == 15
    assert d.W_STU_CAMPUS_STAY == 1
    assert d.W_RES_CLASSROOM == 5
    assert d.W_RES_LAB == 3


def test_default_returns_fresh_mutable_copies():
    d1 = DataBundle.default()
    d2 = DataBundle.default()
    d1.THEORY_SUBJ[0]['weekly'] = 999
    assert d2.THEORY_SUBJ[0]['weekly'] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_bundle.py -v`
Expected: FAIL with `ImportError: cannot import name 'DataBundle' from 'data'` (or similar — the
current `data.py` has no `DataBundle`).

- [ ] **Step 3: Write the implementation**

Replace the full contents of `data.py` with:

```python
"""
data.py — DataBundle: the input data for the University Timetable Scheduling System,
as an explicit, parameterizable object instead of module-level globals.

DataBundle.default() holds today's hardcoded DJSCE-shaped dataset (divisions, batches,
teachers, subjects, rooms, constraint parameters) — the same values `data.py` used to
export as globals, now returned as a fresh object each call so callers can freely mutate
their own copy without affecting others.
"""

from dataclasses import dataclass, field


@dataclass
class DataBundle:
    # --- TIME STRUCTURE ---
    DAYS: list
    NUM_DAYS: int
    SLOT_NAMES: list
    NUM_SLOTS: int
    ACADEMIC_SLOTS: list
    LAB_START_SLOTS: list
    MORNING_SLOTS: list
    AFTERNOON_SLOTS: list
    LAST_SLOT: int

    # --- DIVISIONS & BATCHES ---
    DIVISIONS: list
    NUM_DIVS: int
    BATCHES: list
    NUM_BATCHES: int
    BATCH_TO_DIV: list
    DIV_TO_BATCHES: list
    SIBLING_PAIRS: list

    # --- ROOMS ---
    CLASSROOMS: list
    NUM_CLASSROOMS: int
    LABS_LIST: list
    NUM_LABS: int

    # --- SUBJECTS ---
    THEORY_SUBJ: list
    NUM_THEORY_SUBJ: int
    LAB_SUBJ: list
    NUM_LAB_SUBJ: int

    # --- TEACHERS ---
    ALL_TEACHERS: list

    # --- THEORY <-> LAB PAIRS ---
    THEORY_LAB_PAIRS: list

    # --- DAILY HOUR CONSTRAINTS ---
    MIN_HOURS_PER_DAY: int
    MAX_HOURS_PER_DAY: int

    # --- DIFFICULT SUBJECTS ---
    DIFFICULT_SUBJ_IDX: set

    # --- SOFT CONSTRAINT WEIGHTS ---
    W_FAC_GAP: int
    W_FAC_OVERLOAD: int
    W_FAC_H1: int
    W_FAC_H9: int
    W_FAC_CONSEC: int
    W_STU_CONSEC_DIFF: int
    W_STU_THEORY_H9: int
    W_STU_3DAYS_SAME: int
    W_STU_CAMPUS_STAY: int
    W_RES_CLASSROOM: int
    W_RES_LAB: int

    @staticmethod
    def default() -> "DataBundle":
        num_slots = 9
        academic_slots = list(range(num_slots))
        lab_start_slots = [s for s in academic_slots if (s + 1) in academic_slots]

        theory_subj = [
            {'name': 'DS', 'weekly': 4, 'day_edges_only': False,
             'teachers': {0: 'NM', 1: 'RP', 2: 'SAM'}},
            {'name': 'ML-I', 'weekly': 3, 'day_edges_only': False,
             'teachers': {0: 'KRS', 1: 'SSM', 2: 'KRS'}},
            {'name': 'SDS', 'weekly': 2, 'day_edges_only': False,
             'teachers': {0: 'AB', 1: 'MA', 2: 'NP'}},
            {'name': 'EFM', 'weekly': 2, 'day_edges_only': False,
             'teachers': {0: 'PT', 1: 'AG', 2: 'AG'}},
            {'name': 'CMPM', 'weekly': 2, 'day_edges_only': True,
             'teachers': {0: 'AVG', 1: 'MAA', 2: 'RP'}},
        ]

        lab_subj = [
            {'name': 'DS-Lab', 'twice': False, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'NM', 1: 'NM', 2: 'RP', 3: 'RP', 4: 'SAM', 5: 'SAM'}},
            {'name': 'ML-Lab', 'twice': False, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'KRS', 1: 'KRS', 2: 'SSM', 3: 'SSM', 4: 'KRS', 5: 'KRS'}},
            {'name': 'SDS-Lab', 'twice': False, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'AB', 1: 'AB', 2: 'MA', 3: 'MA', 4: 'NP', 5: 'NP'}},
            {'name': 'WE-Lab', 'twice': True, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'GW', 1: 'GW', 2: 'GW', 3: 'GW', 4: 'GW', 5: 'GW'}},
            {'name': 'PBC-Lab', 'twice': False, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'KT', 1: 'KT', 2: 'KT', 3: 'KT', 4: 'RVP', 5: 'RVP'}},
            {'name': 'CMPM-Lab', 'twice': False, 'sibling_sync': True, 'day_edges_only': True,
             'teachers': {0: 'AVG', 1: 'MAA', 2: 'MAA', 3: 'AVG', 4: 'RP', 5: 'AVG'}},
        ]

        all_teachers = sorted({
            t for s in theory_subj for t in s['teachers'].values()
        } | {
            t for s in lab_subj for t in s['teachers'].values()
        })

        theory_lab_pairs = [(0, 0), (1, 1), (2, 2), (4, 5)]

        return DataBundle(
            DAYS=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            NUM_DAYS=5,
            SLOT_NAMES=['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9'],
            NUM_SLOTS=num_slots,
            ACADEMIC_SLOTS=academic_slots,
            LAB_START_SLOTS=lab_start_slots,
            MORNING_SLOTS=[0, 1, 2, 3],
            AFTERNOON_SLOTS=[5, 6, 7, 8],
            LAST_SLOT=8,

            DIVISIONS=['D1', 'D2', 'D3'],
            NUM_DIVS=3,
            BATCHES=['B1', 'B2', 'B3', 'B4', 'B5', 'B6'],
            NUM_BATCHES=6,
            BATCH_TO_DIV=[0, 0, 1, 1, 2, 2],
            DIV_TO_BATCHES=[[0, 1], [2, 3], [4, 5]],
            SIBLING_PAIRS=[(0, 1), (2, 3), (4, 5)],

            CLASSROOMS=['Class-D1', 'Class-D2', 'Class-D3'],
            NUM_CLASSROOMS=3,
            LABS_LIST=['Lab-1', 'Lab-2', 'Lab-3', 'Lab-4'],
            NUM_LABS=4,

            THEORY_SUBJ=theory_subj,
            NUM_THEORY_SUBJ=len(theory_subj),
            LAB_SUBJ=lab_subj,
            NUM_LAB_SUBJ=len(lab_subj),

            ALL_TEACHERS=all_teachers,
            THEORY_LAB_PAIRS=theory_lab_pairs,

            MIN_HOURS_PER_DAY=5,
            MAX_HOURS_PER_DAY=8,

            DIFFICULT_SUBJ_IDX={0, 1, 4},

            W_FAC_GAP=8,
            W_FAC_OVERLOAD=5,
            W_FAC_H1=5,
            W_FAC_H9=5,
            W_FAC_CONSEC=10,
            W_STU_CONSEC_DIFF=10,
            W_STU_THEORY_H9=5,
            W_STU_3DAYS_SAME=15,
            W_STU_CAMPUS_STAY=1,
            W_RES_CLASSROOM=5,
            W_RES_LAB=3,
        )
```

Note on the `day_edges_only` field (not in the original spec, discovered while implementing):
`model.py`'s original code had a *third* magic index, `CMPM_THEORY_IDX = 4`, paired with a
"start-or-end-of-day-only" placement rule applied to both the CMPM theory subject and the
CMPM-Lab (`CMPM_LAB_IDX`). Left as a hardcoded index, this would silently break (wrong subject
blocked, or `IndexError`) the moment the dashboard lets someone reorder/add/remove theory
subjects — which contradicts the "full CRUD" dashboard decision. `day_edges_only` generalizes it
to any subject, the same way `twice`/`sibling_sync` generalize `WE_LAB_IDX`/`CMPM_LAB_IDX`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data_bundle.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add data.py tests/__init__.py tests/test_data_bundle.py
git commit -m "refactor: turn data.py into a DataBundle dataclass"
```

---

### Task 2: `model.py` — fix duplication bug, thread `data`, generalize magic indices

**Files:**
- Modify: `model.py` (full rewrite)
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `DataBundle` from Task 1.
- Produces: `build_model(data: DataBundle) -> tuple[cp_model.CpModel, dict]`. `vars_dict` keys are
  unchanged from before: `tv, lv, lr, oe1, oe2, is_break, div_day_hours, faculty_score,
  student_score, resource_score, total_penalty`. Later tasks (`solver.py`,
  `extract_schedule.py`) rely on exactly these keys.

- [ ] **Step 1: Write the failing test**

Create `tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model.py -v`
Expected: FAIL with `TypeError: build_model() takes 0 positional arguments but 1 was given`

- [ ] **Step 3: Write the implementation**

Replace the full contents of `model.py` with:

```python
"""
model.py — CP-SAT model builder.
Creates all decision variables, encodes all 21 hard constraints (HC) and
9 soft penalty terms (SC), then returns the model and variable dictionaries.

Takes a DataBundle (see data.py) instead of importing module-level globals, so the same
builder works against the hardcoded default dataset or a dashboard/DB-driven one.
"""

from ortools.sat.python import cp_model


def build_model(data):
    model = cp_model.CpModel()

    NUM_DAYS = data.NUM_DAYS
    ACADEMIC_SLOTS = data.ACADEMIC_SLOTS
    LAB_START_SLOTS = data.LAB_START_SLOTS
    LAST_SLOT = data.LAST_SLOT
    NUM_DIVS = data.NUM_DIVS
    NUM_BATCHES = data.NUM_BATCHES
    DIV_TO_BATCHES = data.DIV_TO_BATCHES
    SIBLING_PAIRS = data.SIBLING_PAIRS
    NUM_LABS = data.NUM_LABS
    THEORY_SUBJ = data.THEORY_SUBJ
    NUM_THEORY_SUBJ = data.NUM_THEORY_SUBJ
    LAB_SUBJ = data.LAB_SUBJ
    NUM_LAB_SUBJ = data.NUM_LAB_SUBJ
    ALL_TEACHERS = data.ALL_TEACHERS
    THEORY_LAB_PAIRS = data.THEORY_LAB_PAIRS
    DIFFICULT_SUBJ_IDX = data.DIFFICULT_SUBJ_IDX
    MIN_HOURS_PER_DAY = data.MIN_HOURS_PER_DAY
    MAX_HOURS_PER_DAY = data.MAX_HOURS_PER_DAY
    W_FAC_GAP = data.W_FAC_GAP
    W_FAC_OVERLOAD = data.W_FAC_OVERLOAD
    W_FAC_H1 = data.W_FAC_H1
    W_FAC_H9 = data.W_FAC_H9
    W_FAC_CONSEC = data.W_FAC_CONSEC
    W_STU_CONSEC_DIFF = data.W_STU_CONSEC_DIFF
    W_STU_THEORY_H9 = data.W_STU_THEORY_H9
    W_STU_3DAYS_SAME = data.W_STU_3DAYS_SAME
    W_RES_CLASSROOM = data.W_RES_CLASSROOM
    W_RES_LAB = data.W_RES_LAB

    # =========================================================================
    # A.  DECISION VARIABLES
    # =========================================================================

    # --- Theory vars: tv[(div, subj, day, slot)] = 1 iff scheduled ---
    tv = {}
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            for day in range(NUM_DAYS):
                for slot in ACADEMIC_SLOTS:
                    tv[(div, subj, day, slot)] = model.NewBoolVar(
                        f'tv_d{div}_s{subj}_D{day}_h{slot}')

    # --- OE day-selection vars (teacher-free, simultaneous all divisions) ---
    oe1 = [model.NewBoolVar(f'oe1_D{d}') for d in range(NUM_DAYS)]  # 1-hr OE day
    oe2 = [model.NewBoolVar(f'oe2_D{d}') for d in range(NUM_DAYS)]  # 2-hr OE day

    # --- Lab vars: lv[(batch, lab_subj, day, start_slot)] = 1 iff scheduled ---
    lv = {}
    for b in range(NUM_BATCHES):
        for ls in range(NUM_LAB_SUBJ):
            for day in range(NUM_DAYS):
                for ss in LAB_START_SLOTS:
                    lv[(b, ls, day, ss)] = model.NewBoolVar(
                        f'lv_b{b}_ls{ls}_D{day}_ss{ss}')

    # --- Lab room vars: lr[(batch, lab_subj, day, start_slot, room)] = 1 iff assigned ---
    lr = {}
    for b in range(NUM_BATCHES):
        for ls in range(NUM_LAB_SUBJ):
            for day in range(NUM_DAYS):
                for ss in LAB_START_SLOTS:
                    for r in range(NUM_LABS):
                        lr[(b, ls, day, ss, r)] = model.NewBoolVar(
                            f'lr_b{b}_ls{ls}_D{day}_ss{ss}_r{r}')

    # =========================================================================
    # B.  HARD CONSTRAINTS
    # =========================================================================

    # --- Flexible Break vars ---
    is_break = {}
    is_on_campus = {}
    for div in range(NUM_DIVS):
        for day in range(NUM_DAYS):
            for s in range(9):
                is_break[(div, day, s)] = model.NewBoolVar(f'brk_{div}_{day}_{s}')
                is_on_campus[(div, day, s)] = model.NewBoolVar(f'camp_{div}_{day}_{s}')
            # Exactly one break per day
            model.AddExactlyOne(is_break[(div, day, s)] for s in range(9))

            # Break window (after first 2 lectures, before last 2 lectures)
            for s in range(9):
                if s < 2 or s > 9 - 3:
                    model.Add(is_break[(div, day, s)] == 0)
                else:
                    # If break at s, then s-1, s-2, s+1, s+2 must be on campus
                    model.AddImplication(is_break[(div, day, s)], is_on_campus[(div, day, s-1)])
                    model.AddImplication(is_break[(div, day, s)], is_on_campus[(div, day, s-2)])
                    model.AddImplication(is_break[(div, day, s)], is_on_campus[(div, day, s+1)])
                    model.AddImplication(is_break[(div, day, s)], is_on_campus[(div, day, s+2)])

    # ---- HC15 + HC16: OE pattern ----------------------------------------
    # Exactly one 1-hr day and one 2-hr day; must be different days.
    model.AddExactlyOne(oe1)
    model.AddExactlyOne(oe2)
    for d in range(NUM_DAYS):
        model.Add(oe1[d] + oe2[d] <= 1)   # different days for OE patterns

    # ---- HC17: twice-weekly lab subjects run exactly twice per batch per week,
    # on different days. HC18: every other lab subject exactly once. ----------
    twice_weekly_idx = [i for i, s in enumerate(LAB_SUBJ) if s['twice']]
    for b in range(NUM_BATCHES):
        for ls in twice_weekly_idx:
            model.Add(
                sum(lv[(b, ls, d, ss)]
                    for d in range(NUM_DAYS) for ss in LAB_START_SLOTS) == 2)
            for d in range(NUM_DAYS):
                model.Add(
                    sum(lv[(b, ls, d, ss)] for ss in LAB_START_SLOTS) <= 1)

    for b in range(NUM_BATCHES):
        for ls in range(NUM_LAB_SUBJ):
            if ls not in twice_weekly_idx:
                model.Add(
                    sum(lv[(b, ls, d, ss)]
                        for d in range(NUM_DAYS) for ss in LAB_START_SLOTS) == 1)

    # ---- Room assignment: if lab scheduled → exactly one room assigned ------
    for b in range(NUM_BATCHES):
        for ls in range(NUM_LAB_SUBJ):
            for day in range(NUM_DAYS):
                for ss in LAB_START_SLOTS:
                    model.Add(
                        sum(lr[(b, ls, day, ss, r)] for r in range(NUM_LABS))
                        == lv[(b, ls, day, ss)])

    # ---- HC7: No lab-room double-booking ------------------------------------
    # A lab occupies room r at slots ss and ss+1.
    for day in range(NUM_DAYS):
        for slot in ACADEMIC_SLOTS:
            for r in range(NUM_LABS):
                users = [
                    lr[(b, ls, day, ss, r)]
                    for b in range(NUM_BATCHES)
                    for ls in range(NUM_LAB_SUBJ)
                    for ss in LAB_START_SLOTS
                    if ss == slot or ss + 1 == slot
                ]
                if users:
                    model.Add(sum(users) <= 1)

    # ---- Flexible Break Lab consecutive check -------------------------------
    # Lab cannot start if either ss or ss+1 is a break for the batch's division
    for div in range(NUM_DIVS):
        for b in DIV_TO_BATCHES[div]:
            for ls in range(NUM_LAB_SUBJ):
                for day in range(NUM_DAYS):
                    for ss in LAB_START_SLOTS:
                        model.Add(is_break[(div, day, ss)] + is_break[(div, day, ss+1)] == 0).OnlyEnforceIf(lv[(b, ls, day, ss)])

    # ---- HC13/14: Sibling Batch Synchronization (No-Idle Hard Constraint) ------
    # If B1 has a lab at any slot, B2 must also have a lab at the exact same slot.
    for (b1, b2) in SIBLING_PAIRS:
        for day in range(NUM_DAYS):
            for ss in LAB_START_SLOTS:
                model.Add(
                    sum(lv[(b1, ls, day, ss)] for ls in range(NUM_LAB_SUBJ))
                    ==
                    sum(lv[(b2, ls, day, ss)] for ls in range(NUM_LAB_SUBJ))
                )

    # Also enforce HC14: sibling-sync lab subjects start simultaneously for both siblings
    sibling_sync_idx = [i for i, s in enumerate(LAB_SUBJ) if s['sibling_sync']]
    for (b1, b2) in SIBLING_PAIRS:
        for ls in sibling_sync_idx:
            for day in range(NUM_DAYS):
                for ss in LAB_START_SLOTS:
                    model.Add(
                        lv[(b1, ls, day, ss)]
                        == lv[(b2, ls, day, ss)])

    # ---- HC10: No batch clash -----------------------------------------------
    # A batch cannot be in two labs at the same slot.
    for b in range(NUM_BATCHES):
        for day in range(NUM_DAYS):
            for slot in ACADEMIC_SLOTS:
                batch_at_slot = [
                    lv[(b, ls, day, ss)]
                    for ls in range(NUM_LAB_SUBJ)
                    for ss in LAB_START_SLOTS
                    if ss == slot or ss + 1 == slot
                ]
                if batch_at_slot:
                    model.Add(sum(batch_at_slot) <= 1)

    # ---- HC11: Each theory subject at most once per day per division ---------
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            for day in range(NUM_DAYS):
                model.Add(
                    sum(tv[(div, subj, day, slot)] for slot in ACADEMIC_SLOTS) <= 1)

    # ---- HC1 (weekly counts): Required weekly theory lectures ---------------
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            model.Add(
                sum(tv[(div, subj, day, slot)]
                    for day in range(NUM_DAYS) for slot in ACADEMIC_SLOTS)
                == THEORY_SUBJ[subj]['weekly'])

    # ---- HC9 + HC6: No division clash / classroom double-booking -----------
    # (Classrooms are division-dedicated, so div-clash → room-clash equivalent.)
    # Also enforces HC15: OE at H1 (and H2 for 2-hr day) blocks theory there.
    for div in range(NUM_DIVS):
        for day in range(NUM_DAYS):
            for slot in ACADEMIC_SLOTS:
                theory_here = [tv[(div, subj, day, slot)]
                                for subj in range(NUM_THEORY_SUBJ)]
                if slot == 0:     # H1 – blocked on both OE days
                    model.Add(sum(theory_here) + oe1[day] + oe2[day] <= 1)
                elif slot == 1:   # H2 – blocked on 2-hr OE day only
                    model.Add(sum(theory_here) + oe2[day] <= 1)
                else:
                    model.Add(sum(theory_here) <= 1)

    # ---- OE blocks lab starts at H1 (both OE days) and H2 (OE-2hr day) ------
    for day in range(NUM_DAYS):
        for b in range(NUM_BATCHES):
            for ls in range(NUM_LAB_SUBJ):
                # OE1 (1-hr) occupies H1
                if 0 in LAB_START_SLOTS:
                    model.Add(lv[(b, ls, day, 0)] == 0).OnlyEnforceIf(oe1[day])
                # OE2 (2-hr) occupies H1 and H2
                if 0 in LAB_START_SLOTS:
                    model.Add(lv[(b, ls, day, 0)] == 0).OnlyEnforceIf(oe2[day])
                if 1 in LAB_START_SLOTS:
                    model.Add(lv[(b, ls, day, 1)] == 0).OnlyEnforceIf(oe2[day])

    # ---- Day-edges-only constraint (theory): subjects flagged day_edges_only must
    # sit at the start or end of the day, never mid-day -----------------------------
    day_edges_theory_idx = [i for i, s in enumerate(THEORY_SUBJ) if s.get('day_edges_only')]
    for subj in day_edges_theory_idx:
        for div in range(NUM_DIVS):
            for day in range(NUM_DAYS):
                # Block globally from mid-day H3, H4, H5, H6, H7 (indices 2, 3, 4, 5, 6)
                for s in [2, 3, 4, 5, 6]:
                    model.Add(tv[(div, subj, day, s)] == 0)

                # Block from H2 on OE-1hr days to prevent gap for non-flagged-subject students
                model.Add(tv[(div, subj, day, 1)] == 0).OnlyEnforceIf(oe1[day])

    # ---- Day-edges-only constraint (lab): same rule for flagged lab subjects -------
    day_edges_lab_idx = [i for i, s in enumerate(LAB_SUBJ) if s.get('day_edges_only')]
    for ls in day_edges_lab_idx:
        for b in range(NUM_BATCHES):
            for day in range(NUM_DAYS):
                # Block start slots in the mid-day: H3, H4, H5, H6 (indices 2, 3, 4, 5)
                # Allowed start slots: H1 (0), H2 (1) and H7 (6), H8 (7)
                for ss in [2, 3, 4, 5]:
                    if ss in LAB_START_SLOTS:
                        model.Add(lv[(b, ls, day, ss)] == 0)

                # Block from H2 on OE-1hr days to prevent gap for non-flagged-subject students
                if 1 in LAB_START_SLOTS:
                    model.Add(lv[(b, ls, day, 1)] == 0).OnlyEnforceIf(oe1[day])

    # ---- Division-in-lab indicator + no theory during lab -------------------
    # Theory is division-wide — if ANY batch of the division is in lab at slot s,
    # the whole division cannot run theory at that slot (students attending theory
    # must all be present; batch in lab cannot attend theory simultaneously).
    div_in_lab_at = {}   # (div, day, slot) -> BoolVar
    for div in range(NUM_DIVS):
        batches_of_div = DIV_TO_BATCHES[div]   # e.g. [0,1] for D1
        for day in range(NUM_DAYS):
            for slot in ACADEMIC_SLOTS:
                lab_vars = [
                    lv[(b, ls, day, ss)]
                    for b in batches_of_div
                    for ls in range(NUM_LAB_SUBJ)
                    for ss in LAB_START_SLOTS
                    if ss == slot or ss + 1 == slot
                ]
                if lab_vars:
                    dil = model.NewBoolVar(f'dil_{div}_{day}_{slot}')
                    model.AddMaxEquality(dil, lab_vars)   # 1 if ANY batch in lab
                    div_in_lab_at[(div, day, slot)] = dil
                    # No theory for this division during lab slots
                    for subj in range(NUM_THEORY_SUBJ):
                        model.Add(tv[(div, subj, day, slot)] + dil <= 1)

    # ---- HC8: Teacher clash (≤ 1 activity per teacher per day-slot) ---------
    for teacher in ALL_TEACHERS:
        for day in range(NUM_DAYS):
            for slot in ACADEMIC_SLOTS:
                t_vars = []
                # Theory contributions
                for div in range(NUM_DIVS):
                    for subj in range(NUM_THEORY_SUBJ):
                        if THEORY_SUBJ[subj]['teachers'].get(div) == teacher:
                            t_vars.append(tv[(div, subj, day, slot)])
                # Lab contributions — all labs treated uniformly (including sibling-sync labs)
                for b in range(NUM_BATCHES):
                    for ls in range(NUM_LAB_SUBJ):
                        if LAB_SUBJ[ls]['teachers'].get(b) == teacher:
                            for ss in LAB_START_SLOTS:
                                if ss == slot or ss + 1 == slot:
                                    t_vars.append(lv[(b, ls, day, ss)])
                if t_vars:
                    model.Add(sum(t_vars) <= 1)

    # ---- HC21: Theory and lab of same subject cannot overlap ----------------
    for (ts, ls) in THEORY_LAB_PAIRS:
        for div in range(NUM_DIVS):
            b_rep = DIV_TO_BATCHES[div][0]
            for day in range(NUM_DAYS):
                for slot in ACADEMIC_SLOTS:
                    lab_at_slot = [
                        lv[(b_rep, ls, day, ss)]
                        for ss in LAB_START_SLOTS
                        if ss == slot or ss + 1 == slot
                    ]
                    if lab_at_slot:
                        dil = model.NewBoolVar(f'tlc_{div}_{ts}_{day}_{slot}')
                        model.AddMaxEquality(dil, lab_at_slot)
                        model.Add(tv[(div, ts, day, slot)] + dil <= 1)

    # ---- HC1 (daily hours): Each division has MIN..MAX academic hours/day ---
    div_day_hours = {}
    for div in range(NUM_DIVS):
        batches_of_div = DIV_TO_BATCHES[div]   # both batches, e.g. [0,1]
        for day in range(NUM_DAYS):
            terms = []
            # Theory: 1 hr each
            for subj in range(NUM_THEORY_SUBJ):
                for slot in ACADEMIC_SLOTS:
                    terms.append(tv[(div, subj, day, slot)])
            # OE: oe1 day = 1 hr; oe2 day = 2 hrs (add twice)
            terms.append(oe1[day])
            terms.append(oe2[day])
            terms.append(oe2[day])
            # Lab hours: count UNION of both batches' lab blocks (not just b_rep).
            for ss in LAB_START_SLOTS:
                any_lab_at_ss = model.NewBoolVar(f'anylb_{div}_{day}_{ss}')
                lab_at_ss_vars = [
                    lv[(b, ls, day, ss)]
                    for b in batches_of_div
                    for ls in range(NUM_LAB_SUBJ)
                ]
                model.AddMaxEquality(any_lab_at_ss, lab_at_ss_vars)
                # 2 hrs per distinct lab block occupied by division
                terms.append(any_lab_at_ss)
                terms.append(any_lab_at_ss)
            h = model.NewIntVar(0, 16, f'hours_{div}_{day}')
            model.Add(h == sum(terms))
            model.Add(h >= MIN_HOURS_PER_DAY)
            model.Add(h <= MAX_HOURS_PER_DAY)
            div_day_hours[(div, day)] = h

    # ---- HC2: Daily hours must fluctuate (at least 2 different values) ------
    for div in range(NUM_DIVS):
        day_hvars = [div_day_hours[(div, d)] for d in range(NUM_DAYS)]
        min_h = model.NewIntVar(0, 10, f'minh_{div}')
        max_h = model.NewIntVar(0, 10, f'maxh_{div}')
        model.AddMinEquality(min_h, day_hvars)
        model.AddMaxEquality(max_h, day_hvars)
        model.Add(max_h - min_h >= 1)

    # ---- Constraint D (spec): Labs must run on every working day ------------
    for day in range(NUM_DAYS):
        model.Add(
            sum(lv[(b, ls, day, ss)]
                for b in range(NUM_BATCHES)
                for ls in range(NUM_LAB_SUBJ)
                for ss in LAB_START_SLOTS) >= 1)

    # =========================================================================
    # C.  MULTI-OBJECTIVE SCORING
    # =========================================================================
    faculty_penalties = []
    student_penalties = []
    resource_penalties = []

    # -------------------------------------------------------------------------
    # FACULTY SCORE
    # -------------------------------------------------------------------------
    for teacher in ALL_TEACHERS:
        ta = {}
        daily_load = []
        for day in range(NUM_DAYS):
            load_terms = []
            for slot in ACADEMIC_SLOTS:
                t_vars = []
                for div in range(NUM_DIVS):
                    for subj in range(NUM_THEORY_SUBJ):
                        if THEORY_SUBJ[subj]['teachers'].get(div) == teacher:
                            t_vars.append(tv[(div, subj, day, slot)])
                for b in range(NUM_BATCHES):
                    for ls in range(NUM_LAB_SUBJ):
                        if LAB_SUBJ[ls]['teachers'].get(b) == teacher:
                            for ss in LAB_START_SLOTS:
                                if ss == slot or ss + 1 == slot:
                                    t_vars.append(lv[(b, ls, day, ss)])
                if t_vars:
                    act = model.NewBoolVar(f'ta_{teacher}_{day}_{slot}')
                    model.Add(sum(t_vars) >= 1).OnlyEnforceIf(act)
                    model.Add(sum(t_vars) == 0).OnlyEnforceIf(act.Not())
                    ta[(day, slot)] = act
                    load_terms.append(act)

            if load_terms:
                ld = model.NewIntVar(0, 12, f'fac_ld_{teacher}_{day}')
                model.Add(ld == sum(load_terms))
                daily_load.append(ld)

                overload = model.NewIntVar(0, 12, f'fac_over_{teacher}_{day}')
                model.AddMaxEquality(overload, [0, ld - 4])
                faculty_penalties.append(W_FAC_OVERLOAD * overload)

        consec_triples = [(0, 1, 2), (1, 2, 3), (5, 6, 7), (6, 7, 8)]
        for day in range(NUM_DAYS):
            for (s1, s2, s3) in consec_triples:
                if (day, s1) in ta and (day, s2) in ta and (day, s3) in ta:
                    consec3 = model.NewBoolVar(f'fac_c3_{teacher}_{day}_{s1}')
                    model.AddBoolAnd([ta[(day, s1)], ta[(day, s2)], ta[(day, s3)]]).OnlyEnforceIf(consec3)
                    model.AddBoolOr([ta[(day, s1)].Not(), ta[(day, s2)].Not(), ta[(day, s3)].Not()]).OnlyEnforceIf(consec3.Not())
                    faculty_penalties.append(W_FAC_CONSEC * consec3)

        for day in range(NUM_DAYS):
            for (s1, s2, s3) in consec_triples:
                if (day, s1) in ta and (day, s2) in ta and (day, s3) in ta:
                    gap = model.NewBoolVar(f'fac_gap_{teacher}_{day}_{s1}')
                    model.AddBoolAnd([ta[(day, s1)], ta[(day, s2)].Not(), ta[(day, s3)]]).OnlyEnforceIf(gap)
                    model.AddBoolOr([ta[(day, s1)].Not(), ta[(day, s2)], ta[(day, s3)].Not()]).OnlyEnforceIf(gap.Not())
                    faculty_penalties.append(W_FAC_GAP * gap)

        for day in range(NUM_DAYS):
            if (day, 0) in ta:
                faculty_penalties.append(W_FAC_H1 * ta[(day, 0)])
            if (day, LAST_SLOT) in ta:
                faculty_penalties.append(W_FAC_H9 * ta[(day, LAST_SLOT)])

    # -------------------------------------------------------------------------
    # STUDENT SCORE
    # -------------------------------------------------------------------------
    active_physical = {}
    for div in range(NUM_DIVS):
        for day in range(NUM_DAYS):
            for s in range(9):
                act_s = model.NewBoolVar(f'stu_act_{div}_{day}_{s}')
                terms = []
                for subj in range(NUM_THEORY_SUBJ):
                    terms.append(tv[(div, subj, day, s)])
                for b in DIV_TO_BATCHES[div]:
                    for ls in range(NUM_LAB_SUBJ):
                        for ss in LAB_START_SLOTS:
                            if ss == s or ss + 1 == s:
                                terms.append(lv[(b, ls, day, ss)])
                if s == 0:
                    terms.append(oe1[day])
                if s in (0, 1):
                    terms.append(oe2[day])

                if terms:
                    model.Add(sum(terms) >= 1).OnlyEnforceIf(act_s)
                    model.Add(sum(terms) == 0).OnlyEnforceIf(act_s.Not())
                else:
                    model.Add(act_s == 0)
                active_physical[(div, day, s)] = act_s

                model.Add(act_s == 0).OnlyEnforceIf(is_break[(div, day, s)])
                model.Add(is_on_campus[(div, day, s)] == act_s + is_break[(div, day, s)])

            model.Add(sum(is_on_campus[(div, day, s)] for s in range(9)) == div_day_hours[(div, day)] + 1)

            # ST1: HARD CONSTRAINT: Student No-Gap
            for s in range(9):
                before_empty = model.NewBoolVar(f'stu_be_{div}_{day}_{s}')
                after_empty = model.NewBoolVar(f'stu_ae_{div}_{day}_{s}')

                if s == 0:
                    model.Add(before_empty == 1)
                else:
                    model.Add(sum(is_on_campus[(div, day, i)] for i in range(0, s)) == 0).OnlyEnforceIf(before_empty)
                    model.Add(sum(is_on_campus[(div, day, i)] for i in range(0, s)) > 0).OnlyEnforceIf(before_empty.Not())

                if s == 8:
                    model.Add(after_empty == 1)
                else:
                    model.Add(sum(is_on_campus[(div, day, i)] for i in range(s+1, 9)) == 0).OnlyEnforceIf(after_empty)
                    model.Add(sum(is_on_campus[(div, day, i)] for i in range(s+1, 9)) > 0).OnlyEnforceIf(after_empty.Not())

                model.AddBoolOr([is_on_campus[(div, day, s)], before_empty, after_empty])

    # ST2: >2 consecutive difficult subjects
    consec_triples = [(0, 1, 2), (1, 2, 3), (5, 6, 7), (6, 7, 8)]
    for div in range(NUM_DIVS):
        for day in range(NUM_DAYS):
            for (s1, s2, s3) in consec_triples:
                diff_flags = []
                for slot in (s1, s2, s3):
                    is_diff = model.NewBoolVar(f'stu_s4_{div}_{day}_{slot}')
                    diff_here = [tv[(div, subj, day, slot)] for subj in DIFFICULT_SUBJ_IDX]
                    model.Add(sum(diff_here) >= 1).OnlyEnforceIf(is_diff)
                    model.Add(sum(diff_here) == 0).OnlyEnforceIf(is_diff.Not())
                    diff_flags.append(is_diff)
                all_diff = model.NewBoolVar(f'stu_s4all_{div}_{day}_{s1}')
                model.AddBoolAnd(diff_flags).OnlyEnforceIf(all_diff)
                model.AddBoolOr([v.Not() for v in diff_flags]).OnlyEnforceIf(all_diff.Not())
                student_penalties.append(W_STU_CONSEC_DIFF * all_diff)

    # ST3: Theory in H9 penalty
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            for day in range(NUM_DAYS):
                student_penalties.append(W_STU_THEORY_H9 * tv[(div, subj, day, LAST_SLOT)])

    # ST4: Same theory subject on 3+ consecutive days penalty
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            for day in range(NUM_DAYS - 2):
                d1_act = model.NewBoolVar(f'stu_3d_{div}_{subj}_{day}')
                model.Add(sum(tv[(div, subj, day, s)] for s in ACADEMIC_SLOTS) >= 1).OnlyEnforceIf(d1_act)
                model.Add(sum(tv[(div, subj, day, s)] for s in ACADEMIC_SLOTS) == 0).OnlyEnforceIf(d1_act.Not())

                d2_act = model.NewBoolVar(f'stu_3d_{div}_{subj}_{day+1}')
                model.Add(sum(tv[(div, subj, day+1, s)] for s in ACADEMIC_SLOTS) >= 1).OnlyEnforceIf(d2_act)
                model.Add(sum(tv[(div, subj, day+1, s)] for s in ACADEMIC_SLOTS) == 0).OnlyEnforceIf(d2_act.Not())

                d3_act = model.NewBoolVar(f'stu_3d_{div}_{subj}_{day+2}')
                model.Add(sum(tv[(div, subj, day+2, s)] for s in ACADEMIC_SLOTS) >= 1).OnlyEnforceIf(d3_act)
                model.Add(sum(tv[(div, subj, day+2, s)] for s in ACADEMIC_SLOTS) == 0).OnlyEnforceIf(d3_act.Not())

                consec3 = model.NewBoolVar(f'stu_c3_{div}_{subj}_{day}')
                model.AddBoolAnd([d1_act, d2_act, d3_act]).OnlyEnforceIf(consec3)
                model.AddBoolOr([d1_act.Not(), d2_act.Not(), d3_act.Not()]).OnlyEnforceIf(consec3.Not())
                student_penalties.append(W_STU_3DAYS_SAME * consec3)

    # -------------------------------------------------------------------------
    # RESOURCE SCORE
    # -------------------------------------------------------------------------
    cr_totals = []
    for div in range(NUM_DIVS):
        cu = model.NewIntVar(0, 100, f'res_cu_{div}')
        cr_terms = []
        for subj in range(NUM_THEORY_SUBJ):
            for day in range(NUM_DAYS):
                for s in ACADEMIC_SLOTS:
                    cr_terms.append(tv[(div, subj, day, s)])
        cr_terms.append(sum(oe1))
        cr_terms.append(sum(oe2) * 2)
        model.Add(cu == sum(cr_terms))
        cr_totals.append(cu)

    cu_max = model.NewIntVar(0, 100, 'res_cumax')
    cu_min = model.NewIntVar(0, 100, 'res_cumin')
    model.AddMaxEquality(cu_max, cr_totals)
    model.AddMinEquality(cu_min, cr_totals)
    resource_penalties.append(W_RES_CLASSROOM * (cu_max - cu_min))

    room_totals = []
    for r in range(NUM_LABS):
        ru = model.NewIntVar(0, 200, f'res_ru_{r}')
        model.Add(ru == sum(lr[(b, ls, d, ss, r)]
                             for b in range(NUM_BATCHES)
                             for ls in range(NUM_LAB_SUBJ)
                             for d in range(NUM_DAYS)
                             for ss in LAB_START_SLOTS))
        room_totals.append(ru)
    ru_max = model.NewIntVar(0, 200, 'res_rumax')
    ru_min = model.NewIntVar(0, 200, 'res_rumin')
    model.AddMaxEquality(ru_max, room_totals)
    model.AddMinEquality(ru_min, room_totals)
    resource_penalties.append(W_RES_LAB * (ru_max - ru_min))

    # =========================================================================
    # D.  OBJECTIVE — expose 3 scores + minimize their sum
    # =========================================================================
    faculty_score = model.NewIntVar(0, 10_000_000, 'faculty_score')
    student_score = model.NewIntVar(0, 10_000_000, 'student_score')
    resource_score = model.NewIntVar(0, 10_000_000, 'resource_score')

    model.Add(faculty_score == sum(faculty_penalties))
    model.Add(student_score == sum(student_penalties))
    model.Add(resource_score == sum(resource_penalties))

    total_penalty = model.NewIntVar(0, 10_000_000, 'total_penalty')
    model.Add(total_penalty == faculty_score + student_score + resource_score)
    model.Minimize(total_penalty)

    vars_dict = {
        'tv': tv,
        'lv': lv,
        'lr': lr,
        'oe1': oe1,
        'oe2': oe2,
        'is_break': is_break,
        'div_day_hours': div_day_hours,
        'faculty_score': faculty_score,
        'student_score': student_score,
        'resource_score': resource_score,
        'total_penalty': total_penalty,
    }
    return model, vars_dict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_model.py -v -s`
Expected: PASS (2 tests). This takes up to ~40s per test (real CP-SAT solves) — that's expected.

- [ ] **Step 5: Commit**

```bash
git add model.py tests/test_model.py
git commit -m "fix: dedupe model.py objective section, thread DataBundle, generalize magic indices"
```

---

### Task 3: `solver.py` — thread `data`, generalize `CMPM_LAB_IDX` check, add `time_limit_s`

**Files:**
- Modify: `solver.py` (full rewrite)
- Test: `tests/test_solver.py`

**Interfaces:**
- Consumes: `DataBundle` (Task 1), `build_model(data)` (Task 2).
- Produces: `solve_and_report(model, vars_dict, data, time_limit_s=90) -> (solver, status,
  vars_dict)`; `check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours, data) ->
  list[str]`. Both signatures gain a trailing `data` parameter versus today; `solve_and_report`
  additionally gains `time_limit_s` (default 90, preserving current behavior for `main.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_solver.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_solver.py -v -s`
Expected: FAIL with `TypeError` (current `solve_and_report`/`check_hard_violations` don't accept
a `data` argument).

- [ ] **Step 3: Write the implementation**

Replace the full contents of `solver.py` with:

```python
"""
solver.py — Solve the CP-SAT model and print the full solution report.
"""
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model


CELL = 14


def _cell(s):
    return str(s)[:CELL].ljust(CELL)


def _hline(cols):
    return '+' + ('+'.join(['-' * (CELL + 2)] * cols)) + '+'


def _row(cells):
    return '|' + '|'.join(f' {_cell(c)} ' for c in cells) + '|'


def _get_val(solver, var):
    return solver.Value(var)


def _theory_grid(solver, tv, div, day, data):
    grid = {}
    for subj in range(data.NUM_THEORY_SUBJ):
        for slot in data.ACADEMIC_SLOTS:
            if _get_val(solver, tv[(div, subj, day, slot)]):
                t = data.THEORY_SUBJ[subj]['teachers'][div]
                grid[slot] = (data.THEORY_SUBJ[subj]['name'], t)
    return grid


def _lab_grid(solver, lv, lr, batch, day, data):
    grid = {}
    for ls in range(data.NUM_LAB_SUBJ):
        for ss in data.LAB_START_SLOTS:
            if _get_val(solver, lv[(batch, ls, day, ss)]):
                teacher = data.LAB_SUBJ[ls]['teachers'][batch]
                room = next(
                    (data.LABS_LIST[r] for r in range(data.NUM_LABS)
                     if _get_val(solver, lr[(batch, ls, day, ss, r)])),
                    '?'
                )
                lab_name = data.LAB_SUBJ[ls]['name']
                grid[ss] = (lab_name, teacher, room)
                grid[ss+1] = (f'{lab_name}(cont)', teacher, room)
    return grid


def check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours, data):
    violations = []

    # HC1 – Weekly lecture counts
    for div in range(data.NUM_DIVS):
        for subj in range(data.NUM_THEORY_SUBJ):
            count = sum(_get_val(solver, tv[(div, subj, d, s)])
                        for d in range(data.NUM_DAYS) for s in data.ACADEMIC_SLOTS)
            expected = data.THEORY_SUBJ[subj]['weekly']
            if count != expected:
                violations.append(
                    f"HC1 – {data.DIVISIONS[div]} {data.THEORY_SUBJ[subj]['name']}: "
                    f"got {count}, need {expected}")

    # HC2 – Fluctuation
    for div in range(data.NUM_DIVS):
        counts = {_get_val(solver, div_day_hours[(div, d)]) for d in range(data.NUM_DAYS)}
        if len(counts) == 1:
            violations.append(f"HC2 – {data.DIVISIONS[div]}: all days have same hour count ({list(counts)[0]})")

    # HC7 – Lab room double-booking
    for day in range(data.NUM_DAYS):
        for slot in data.ACADEMIC_SLOTS:
            for r in range(data.NUM_LABS):
                users = [
                    (b, ls, ss)
                    for b in range(data.NUM_BATCHES)
                    for ls in range(data.NUM_LAB_SUBJ)
                    for ss in data.LAB_START_SLOTS
                    if (ss == slot or ss + 1 == slot)
                    and _get_val(solver, lr[(b, ls, day, ss, r)])
                ]
                if len(users) > 1:
                    violations.append(
                        f"HC7 – Lab {data.LABS_LIST[r]} double-booked "
                        f"{data.DAYS[day]} {data.SLOT_NAMES[slot]}: {users}")

    # HC8 – Teacher clash
    for teacher in sorted({t for s in data.THEORY_SUBJ for t in s['teachers'].values()} |
                          {t for s in data.LAB_SUBJ for t in s['teachers'].values()}):
        for day in range(data.NUM_DAYS):
            for slot in data.ACADEMIC_SLOTS:
                cnt = 0
                for div in range(data.NUM_DIVS):
                    for subj in range(data.NUM_THEORY_SUBJ):
                        if data.THEORY_SUBJ[subj]['teachers'].get(div) == teacher:
                            cnt += _get_val(solver, tv[(div, subj, day, slot)])
                for b in range(data.NUM_BATCHES):
                    for ls in range(data.NUM_LAB_SUBJ):
                        if data.LAB_SUBJ[ls]['teachers'].get(b) == teacher:
                            for ss in data.LAB_START_SLOTS:
                                if ss == slot or ss + 1 == slot:
                                    cnt += _get_val(solver, lv[(b, ls, day, ss)])
                if cnt > 1:
                    violations.append(
                        f"HC8 – Teacher {teacher} clash: "
                        f"{data.DAYS[day]} {data.SLOT_NAMES[slot]} (count={cnt})")

    # HC16/HC17 – OE pattern
    oe1_days = [d for d in range(data.NUM_DAYS) if _get_val(solver, oe1[d])]
    oe2_days = [d for d in range(data.NUM_DAYS) if _get_val(solver, oe2[d])]
    if len(oe1_days) != 1:
        violations.append(f"HC16 – Expected 1 OE-1hr day, got {oe1_days}")
    if len(oe2_days) != 1:
        violations.append(f"HC16 – Expected 1 OE-2hr day, got {oe2_days}")
    if oe1_days and oe2_days and oe1_days[0] == oe2_days[0]:
        violations.append(f"HC16 – OE-1hr and OE-2hr on same day ({oe1_days[0]})")

    # HC17 – twice-weekly labs run exactly twice per week, on different days
    twice_weekly_idx = [i for i, s in enumerate(data.LAB_SUBJ) if s['twice']]
    for b in range(data.NUM_BATCHES):
        for ls in twice_weekly_idx:
            cnt = sum(_get_val(solver, lv[(b, ls, d, ss)])
                      for d in range(data.NUM_DAYS) for ss in data.LAB_START_SLOTS)
            if cnt != 2:
                violations.append(f"HC17 – {data.BATCHES[b]} {data.LAB_SUBJ[ls]['name']}: {cnt} sessions (need 2)")
            we_days = [d for d in range(data.NUM_DAYS)
                       if any(_get_val(solver, lv[(b, ls, d, ss)])
                              for ss in data.LAB_START_SLOTS)]
            if len(we_days) != len(set(we_days)):
                violations.append(f"HC17 – {data.BATCHES[b]} {data.LAB_SUBJ[ls]['name']} on same day twice")

    # HC18 – Other labs exactly once
    for b in range(data.NUM_BATCHES):
        for ls in range(data.NUM_LAB_SUBJ):
            if ls in twice_weekly_idx:
                continue
            cnt = sum(_get_val(solver, lv[(b, ls, d, ss)])
                      for d in range(data.NUM_DAYS) for ss in data.LAB_START_SLOTS)
            if cnt != 1:
                violations.append(
                    f"HC18 – {data.BATCHES[b]} {data.LAB_SUBJ[ls]['name']}: {cnt} sessions (need 1)")

    # HC14 – sibling-sync lab subjects must start simultaneously
    sibling_sync_idx = [i for i, s in enumerate(data.LAB_SUBJ) if s['sibling_sync']]
    for (b1, b2) in data.SIBLING_PAIRS:
        for ls in sibling_sync_idx:
            for day in range(data.NUM_DAYS):
                for ss in data.LAB_START_SLOTS:
                    v1 = _get_val(solver, lv[(b1, ls, day, ss)])
                    v2 = _get_val(solver, lv[(b2, ls, day, ss)])
                    if v1 != v2:
                        violations.append(
                            f"HC14 – {data.LAB_SUBJ[ls]['name']} {data.BATCHES[b1]}/{data.BATCHES[b2]} desync "
                            f"{data.DAYS[day]} {data.SLOT_NAMES[ss]}: {v1} vs {v2}")

    return violations


def _print_div_timetable(solver, tv, oe1, oe2, lv, lr, is_break, div, data):
    oe1_day = next((d for d in range(data.NUM_DAYS) if _get_val(solver, oe1[d])), None)
    oe2_day = next((d for d in range(data.NUM_DAYS) if _get_val(solver, oe2[d])), None)

    div_name = data.DIVISIONS[div]
    classroom = data.CLASSROOMS[div]
    batches = data.DIV_TO_BATCHES[div]

    print(f"\n{'='*80}")
    print(f"  TIMETABLE — Division {div_name}   (Classroom: {classroom})")
    print(f"{'='*80}")

    cols = 1 + data.NUM_DAYS
    print(_hline(cols))
    print(_row(['Slot'] + data.DAYS))
    print(_hline(cols))

    for slot in range(data.NUM_SLOTS):
        sname = data.SLOT_NAMES[slot]

        row_cells = [sname]
        for day in range(data.NUM_DAYS):
            cell_text = ''
            if _get_val(solver, is_break[(div, day, slot)]):
                cell_text = '--- BREAK ---'
            elif day == oe2_day and slot in (0, 1):
                cell_text = 'OE(2hr)'
            elif day == oe1_day and slot == 0:
                cell_text = 'OE(1hr)'
            else:
                for subj in range(data.NUM_THEORY_SUBJ):
                    if _get_val(solver, tv[(div, subj, day, slot)]):
                        teacher = data.THEORY_SUBJ[subj]['teachers'][div]
                        cell_text = f"{data.THEORY_SUBJ[subj]['name']}({teacher})"
                        break
                if not cell_text:
                    b_rep = batches[0]
                    for ls in range(data.NUM_LAB_SUBJ):
                        for ss in data.LAB_START_SLOTS:
                            if (ss == slot or ss + 1 == slot) and \
                               _get_val(solver, lv[(b_rep, ls, day, ss)]):
                                room = next(
                                    (data.LABS_LIST[r] for r in range(data.NUM_LABS)
                                     if _get_val(solver, lr[(b_rep, ls, day, ss, r)])), '?')
                                lname = data.LAB_SUBJ[ls]['name']
                                suffix = '' if ss == slot else '(c)'
                                cell_text = f"{lname}{suffix}"

            row_cells.append(cell_text if cell_text else '.')
        print(_row(row_cells))

    print(_hline(cols))


def _print_batch_timetables(solver, lv, lr, data):
    print(f"\n{'='*80}")
    print("  BATCH LAB TIMETABLES")
    print(f"{'='*80}")
    for b in range(data.NUM_BATCHES):
        print(f"\n  Batch {data.BATCHES[b]}:")
        print(f"  {'Day':<12} {'Slot':<6} {'Lab':<12} {'Teacher':<8} {'Room'}")
        print(f"  {'-'*55}")
        for day in range(data.NUM_DAYS):
            for ls in range(data.NUM_LAB_SUBJ):
                for ss in data.LAB_START_SLOTS:
                    if _get_val(solver, lv[(b, ls, day, ss)]):
                        teacher = data.LAB_SUBJ[ls]['teachers'][b]
                        room = next(
                            (data.LABS_LIST[r] for r in range(data.NUM_LABS)
                             if _get_val(solver, lr[(b, ls, day, ss, r)])), '?')
                        print(f"  {data.DAYS[day]:<12} {data.SLOT_NAMES[ss]:<6} "
                              f"{data.LAB_SUBJ[ls]['name']:<12} {teacher:<8} {room}")


def solve_and_report(model, vars_dict, data, time_limit_s=90):
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = time_limit_s

    tv = vars_dict['tv']
    oe1 = vars_dict['oe1']
    oe2 = vars_dict['oe2']
    lv = vars_dict['lv']
    lr = vars_dict['lr']
    div_day_hours = vars_dict['div_day_hours']

    print("\nSolving … (this may take a few minutes for a large model)\n")
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    print("\n" + "=" * 80)
    print("  === SOLUTION REPORT ===")
    print("=" * 80)
    print(f"  Status : {status_name}")
    print(f"  Wall time : {solver.WallTime():.2f} s")

    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        print(f"  Objective (total penalty) : {solver.ObjectiveValue():.0f}")

        print("\n--- MULTI-OBJECTIVE SCORES ---")
        try:
            f_score = solver.Value(vars_dict['faculty_score'])
            s_score = solver.Value(vars_dict['student_score'])
            r_score = solver.Value(vars_dict['resource_score'])
            print(f"  Faculty Score  : {f_score}")
            print(f"  Student Score  : {s_score}")
            print(f"  Resource Score : {r_score}")
            print(f"  Total Penalty  : {f_score + s_score}")
        except KeyError:
            print("  [Legacy mode] Scores not extracted.")

        print("\n--- HARD CONSTRAINT VIOLATIONS (target: 0) ---")
        violations = check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours, data)
        if violations:
            for v in violations:
                print(f"  [FAIL]  {v}")
        else:
            print("  [OK]  No hard violations detected.")
        print(f"  Total hard violations: {len(violations)}")

        print("\n--- DAILY ACADEMIC HOURS PER DIVISION ---")
        print(f"  {'':8}", end='')
        for d in data.DAYS:
            print(f"{d:>6}", end='')
        print()
        for div in range(data.NUM_DIVS):
            print(f"  {data.DIVISIONS[div]:8}", end='')
            for day in range(data.NUM_DAYS):
                h = solver.Value(div_day_hours[(div, day)])
                print(f"{h:>6}", end='')
            print()

        oe1_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe1[d])), None)
        oe2_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe2[d])), None)
        print(f"\n  OE 1-hr  : {data.DAYS[oe1_day] if oe1_day is not None else 'NONE'} @ H1")
        print(f"  OE 2-hr  : {data.DAYS[oe2_day] if oe2_day is not None else 'NONE'} @ H1-H2")

        is_break = vars_dict['is_break']
        for div in range(data.NUM_DIVS):
            _print_div_timetable(solver, tv, oe1, oe2, lv, lr, is_break, div, data)

        _print_batch_timetables(solver, lv, lr, data)

    elif status == cp_model.INFEASIBLE:
        print("\n  *** MODEL IS INFEASIBLE ***")
        print("  The solver proved no feasible solution exists under the given constraints.")

    else:
        print(f"\n  Solver returned status: {status_name}")

    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80 + "\n")

    return solver, status, vars_dict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_solver.py -v -s`
Expected: PASS. Takes up to ~40s (real solve).

- [ ] **Step 5: Commit**

```bash
git add solver.py tests/test_solver.py
git commit -m "refactor: thread DataBundle through solver.py, generalize HC14/HC17 checks"
```

---

### Task 4: `extract_schedule.py` — thread `data`

**Files:**
- Modify: `extract_schedule.py` (full rewrite)
- Test: `tests/test_extract_schedule.py`

**Interfaces:**
- Consumes: `DataBundle` (Task 1), a solved `(solver, vars_dict)` pair (Tasks 2–3).
- Produces: `extract_schedule(solver, vars_dict, data) -> dict` with keys `divisions, teachers,
  classrooms, labs` — same shape as before. `pareto.py` (Task 5) and the future compare UI both
  read this shape.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_schedule.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_extract_schedule.py -v -s`
Expected: FAIL with `TypeError: extract_schedule() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Write the implementation**

Replace the full contents of `extract_schedule.py` with:

```python
def extract_schedule(solver, vars_dict, data):
    schedule_data = {
        "divisions": [],
        "teachers": {},
        "classrooms": {},
        "labs": {}
    }

    tv = vars_dict['tv']
    oe1 = vars_dict['oe1']
    oe2 = vars_dict['oe2']
    lv = vars_dict['lv']
    lr = vars_dict['lr']
    is_break = vars_dict['is_break']

    oe1_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe1[d])), None)
    oe2_day = next((d for d in range(data.NUM_DAYS) if solver.Value(oe2[d])), None)

    for t in data.ALL_TEACHERS:
        schedule_data["teachers"][t] = []
    for c in data.CLASSROOMS:
        schedule_data["classrooms"][c] = []
    for r in data.LABS_LIST:
        schedule_data["labs"][r] = []

    def add_entry(entry):
        t = entry.get("teacher")
        if t in schedule_data["teachers"]:
            schedule_data["teachers"][t].append(entry)
        c = entry.get("room")
        if c in schedule_data["classrooms"]:
            schedule_data["classrooms"][c].append(entry)
        if c in schedule_data["labs"]:
            schedule_data["labs"][c].append(entry)

    for div in range(data.NUM_DIVS):
        div_info = {
            "name": data.DIVISIONS[div],
            "classroom": data.CLASSROOMS[div],
            "timetable": []
        }

        for day in range(data.NUM_DAYS):
            for slot in range(data.NUM_SLOTS):
                if solver.Value(is_break[(div, day, slot)]):
                    entry = {"day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "break", "subject": "--- BREAK ---", "division": data.DIVISIONS[div]}
                    div_info["timetable"].append(entry)
                    continue

                added = False

                # 1. LABS (Highest Priority)
                batches_in_lab = []
                for b in data.DIV_TO_BATCHES[div]:
                    for ls in range(data.NUM_LAB_SUBJ):
                        for ss in data.LAB_START_SLOTS:
                            if ss == slot or ss + 1 == slot:
                                if solver.Value(lv[(b, ls, day, ss)]):
                                    room_idx = next(r for r in range(data.NUM_LABS) if solver.Value(lr[(b, ls, day, ss, r)]))
                                    teacher = data.LAB_SUBJ[ls]['teachers'].get(b)
                                    is_cont = (ss + 1 == slot)

                                    b_entry = {
                                        "day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "lab",
                                        "subject": data.LAB_SUBJ[ls]['name'] + (" (cont.)" if is_cont else ""),
                                        "teacher": teacher, "room": data.LABS_LIST[room_idx],
                                        "batch": data.BATCHES[b], "division": data.DIVISIONS[div],
                                        "is_cont": is_cont
                                    }
                                    batches_in_lab.append(b_entry)
                                    add_entry(b_entry)
                if batches_in_lab:
                    subj_str = " | ".join([f"{x['batch']}:{x['subject']}" for x in batches_in_lab])
                    t_str = " | ".join([f"{x['teacher']}" for x in batches_in_lab])
                    r_str = " | ".join([f"{x['room']}" for x in batches_in_lab])
                    is_cont_group = any(x.get("is_cont") for x in batches_in_lab)
                    entry = {
                        "day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "lab",
                        "subject": subj_str, "teacher": t_str, "room": r_str,
                        "division": data.DIVISIONS[div], "batches": batches_in_lab,
                        "is_cont": is_cont_group
                    }
                    div_info["timetable"].append(entry)
                    added = True

                # 2. THEORY (Only if no lab)
                if not added and slot in data.ACADEMIC_SLOTS:
                    for subj in range(data.NUM_THEORY_SUBJ):
                        if solver.Value(tv[(div, subj, day, slot)]):
                            teacher = data.THEORY_SUBJ[subj]['teachers'].get(div)
                            entry = {
                                "day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "theory",
                                "subject": data.THEORY_SUBJ[subj]['name'], "teacher": teacher,
                                "room": data.CLASSROOMS[div], "division": data.DIVISIONS[div]
                            }
                            div_info["timetable"].append(entry)
                            add_entry(entry)
                            added = True
                            break

                # 3. OE (Only if no lab or theory)
                if not added:
                    if day == oe1_day and slot == 0:
                        entry = {"day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "oe", "subject": "OE(1hr)", "room": data.CLASSROOMS[div], "division": data.DIVISIONS[div]}
                        div_info["timetable"].append(entry)
                        add_entry(entry)
                        added = True
                    elif day == oe2_day and slot in (0, 1):
                        entry = {"day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "oe", "subject": "OE(2hr)", "room": data.CLASSROOMS[div], "division": data.DIVISIONS[div]}
                        div_info["timetable"].append(entry)
                        add_entry(entry)
                        added = True

                if not added:
                    entry = {"day": data.DAYS[day], "slot": data.SLOT_NAMES[slot], "type": "empty", "subject": ".", "division": data.DIVISIONS[div]}
                    div_info["timetable"].append(entry)

        schedule_data["divisions"].append(div_info)

    return schedule_data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_extract_schedule.py -v -s`
Expected: PASS. Takes up to ~40s (real solve).

- [ ] **Step 5: Commit**

```bash
git add extract_schedule.py tests/test_extract_schedule.py
git commit -m "refactor: thread DataBundle through extract_schedule.py"
```

---

### Task 5: Update `main.py`, `pareto.py`, `pareto_diagnostic.py` call sites; delete dead files

**Files:**
- Modify: `main.py`, `pareto.py`, `pareto_diagnostic.py`
- Delete: `fix_model.py`, `model_modified.py`
- Test: manual (see Step 4 below) — these are thin CLI wrappers over already-tested pieces
  (Tasks 2–4), so no new automated test is added here; a full run is a slow (~90s) integration
  smoke test better done once by hand than on every `pytest` run.

**Interfaces:**
- Consumes: `DataBundle.default()`, `build_model(data)`, `solve_and_report(model, vars_dict,
  data, time_limit_s=...)`, `extract_schedule(solver, vars_dict, data)` — all from Tasks 1–4.

- [ ] **Step 1: Update `main.py`**

Replace the full contents of `main.py` with:

```python
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

    err = model.Validate()
    if err:
        print(f"\n  [!] Model validation error:\n  {err}")
        return

    print("      Model built and validated successfully.")
    print("\n[2/2] Launching solver …\n")
    solve_and_report(model, vars_dict, data)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Update `pareto.py`**

Replace the full contents of `pareto.py` with:

```python
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

    import json
    with open("webapp/pareto_solutions.json", "w") as f:
        json.dump(solutions, f, indent=4)


if __name__ == '__main__':
    generate_pareto_front()
```

(Note: epsilon bounds `e_stu`/`e_fac` stay hardcoded here — the dynamic-baseline fix is a later
plan, per the design spec §10 / phase 6. This step only fixes the `build_model()` call site so
the script keeps working.)

- [ ] **Step 3: Update `pareto_diagnostic.py`**

Replace the full contents of `pareto_diagnostic.py` with:

```python
import sys, io, time
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model
from data import DataBundle
from model import build_model


def run_diagnostic():
    print("============================================================")
    print("  DIAGNOSTIC RUN: Epsilon-Constraint Bounds Test")
    print("============================================================")

    data = DataBundle.default()

    # Set 1: Minimize Faculty, bound Student <= 250
    model1, vars1 = build_model(data)
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
    model2, vars2 = build_model(data)
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
    model3, vars3 = build_model(data)
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
```

- [ ] **Step 4: Manual smoke test**

Run: `python main.py`
Expected: completes (up to ~90s), prints `[OK]  No hard violations detected.` and a
`Total hard violations: 0` line, followed by the division timetables. Confirm the printed
`Student Score` is now a single, non-doubled number (the bug fix) — no specific value to check,
just that the run completes cleanly end to end.

- [ ] **Step 5: Delete dead files and commit**

```bash
git rm fix_model.py model_modified.py
git add main.py pareto.py pareto_diagnostic.py
git commit -m "refactor: update CLI/pareto entry points for DataBundle, drop dead migration files"
```

---

### Task 6: `webapp/server.py` — minimal compatibility fix (keep it running, no restructuring yet)

**Files:**
- Modify: `webapp/server.py`

**Interfaces:**
- Consumes: `DataBundle.default()`, `build_model(data)`, `solve_and_report(model, vars_dict,
  data)`, `extract_schedule(solver, vars_dict, data)` — all from Tasks 1–4.
- This task deliberately keeps the current "solve at startup" behavior — moving it to an
  on-demand `POST /api/runs` background job, and adding the DB/dashboard, is the next plan
  (sub-phase 1b/1d of the design spec), not this one. The only change here is passing `data`
  through so the existing server keeps working after Tasks 1–5.

- [ ] **Step 1: Update the startup handler**

In `webapp/server.py`, find:

```python
from data import (
    DAYS, SLOT_NAMES, ACADEMIC_SLOTS, LAB_START_SLOTS,
    NUM_DAYS, NUM_SLOTS,
    DIVISIONS, NUM_DIVS, BATCHES, NUM_BATCHES, DIV_TO_BATCHES,
    CLASSROOMS, LABS_LIST, NUM_LABS,
    THEORY_SUBJ, NUM_THEORY_SUBJ,
    LAB_SUBJ, NUM_LAB_SUBJ, WE_LAB_IDX, CMPM_LAB_IDX,
    MIN_HOURS_PER_DAY, MAX_HOURS_PER_DAY,
    ALL_TEACHERS, THEORY_LAB_PAIRS
)
from model import build_model
from solver import solve_and_report, check_hard_violations
from ortools.sat.python import cp_model
```

Replace with:

```python
from data import DataBundle
from model import build_model
from solver import solve_and_report, check_hard_violations
from ortools.sat.python import cp_model
```

Find:

```python
@app.on_event("startup")
def run_solver():
    global schedule_data
    print("Running solver before starting web server...")
    model, vars_dict = build_model()
    solver, status, _ = solve_and_report(model, vars_dict)

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

    violations = check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours)
```

Replace with:

```python
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
```

Find:

```python
    from extract_schedule import extract_schedule
    extracted = extract_schedule(solver, vars_dict)
```

Replace with:

```python
    from extract_schedule import extract_schedule
    extracted = extract_schedule(solver, vars_dict, data)
```

- [ ] **Step 2: Manual smoke test**

Run: `python -m uvicorn webapp.server:app --port 8760` from the project root, wait for
`Application startup complete` (up to ~90s), then in another terminal:

```bash
curl -s http://127.0.0.1:8760/api/stats
```

Expected: `{"status":"FEASIBLE"...}` (or `OPTIMAL`) with `"hard_violations":0`. Stop the server
afterward (Ctrl+C or kill the process).

- [ ] **Step 3: Commit**

```bash
git add webapp/server.py
git commit -m "refactor: thread DataBundle through webapp/server.py startup solve"
```

---

## Plan self-review notes

- **Spec coverage:** this plan covers spec design-doc §2 (model.py rewrite/dedup) and the
  `DataBundle`/magic-index-generalization half of §4 (model.py refactor). It does **not** cover
  §1 (DB schema), §3 (`scoring.py`), §4's new solvers, §5 (dashboard/compare UI wiring), or §10
  (Pareto dynamic epsilon bounds) — those are follow-up plans, per the phasing in the spec's §12
  and the file-structure note in the writing-plans skill guidance (sequential dependent chain,
  not independent subsystems, but still too large for one plan/session).
- **Placeholder scan:** no TBD/TODO; every step has complete, runnable code.
- **Type consistency:** `DataBundle` field names introduced in Task 1 (`NUM_DIVS`, `THEORY_SUBJ`,
  etc.) are used identically in Tasks 2–6; `build_model(data)`'s `vars_dict` keys are the same
  set consumed by Task 3's `solve_and_report`/`check_hard_violations` and Task 4's
  `extract_schedule`.
