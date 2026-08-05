"""
solver.py — Solve the CP-SAT model and print the full solution report.
"""
import sys, io
# Force UTF-8 output on Windows to avoid cp1252 encode errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from ortools.sat.python import cp_model
from data import (
    DAYS, SLOT_NAMES, ACADEMIC_SLOTS, LAB_START_SLOTS,
    NUM_DAYS, NUM_SLOTS,
    DIVISIONS, NUM_DIVS, BATCHES, NUM_BATCHES, DIV_TO_BATCHES,
    CLASSROOMS, LABS_LIST, NUM_LABS,
    THEORY_SUBJ, NUM_THEORY_SUBJ,
    LAB_SUBJ, NUM_LAB_SUBJ, WE_LAB_IDX, CMPM_LAB_IDX,
    MIN_HOURS_PER_DAY, MAX_HOURS_PER_DAY,
)


# ---------------------------------------------------------------------------
# Helper — pretty fixed-width cell
# ---------------------------------------------------------------------------
CELL = 14

def _cell(s):
    return str(s)[:CELL].ljust(CELL)


def _hline(cols):
    return '+' + ('+'.join(['-' * (CELL + 2)] * cols)) + '+'


def _row(cells):
    return '|' + '|'.join(f' {_cell(c)} ' for c in cells) + '|'


# ---------------------------------------------------------------------------
# Post-solution extraction helpers
# ---------------------------------------------------------------------------

def _get_val(solver, var):
    return solver.Value(var)


def _theory_grid(solver, tv, div, day):
    """Return slot→(subj_name, teacher) for a division on a day."""
    grid = {}
    for subj in range(NUM_THEORY_SUBJ):
        for slot in ACADEMIC_SLOTS:
            if _get_val(solver, tv[(div, subj, day, slot)]):
                t = THEORY_SUBJ[subj]['teachers'][div]
                grid[slot] = (THEORY_SUBJ[subj]['name'], t)
    return grid


def _lab_grid(solver, lv, lr, batch, day):
    """Return slot→(lab_name, teacher, room) for a batch on a day."""
    grid = {}
    for ls in range(NUM_LAB_SUBJ):
        for ss in LAB_START_SLOTS:
            if _get_val(solver, lv[(batch, ls, day, ss)]):
                teacher = LAB_SUBJ[ls]['teachers'][batch]
                room = next(
                    (LABS_LIST[r] for r in range(NUM_LABS)
                     if _get_val(solver, lr[(batch, ls, day, ss, r)])),
                    '?'
                )
                lab_name = LAB_SUBJ[ls]['name']
                grid[ss]   = (lab_name, teacher, room)
                grid[ss+1] = (f'{lab_name}(cont)', teacher, room)
    return grid


# ---------------------------------------------------------------------------
# Hard-constraint violation checker
# ---------------------------------------------------------------------------

def check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours):
    violations = []

    # HC1 – Weekly lecture counts
    for div in range(NUM_DIVS):
        for subj in range(NUM_THEORY_SUBJ):
            count = sum(_get_val(solver, tv[(div, subj, d, s)])
                        for d in range(NUM_DAYS) for s in ACADEMIC_SLOTS)
            expected = THEORY_SUBJ[subj]['weekly']
            if count != expected:
                violations.append(
                    f"HC1 – {DIVISIONS[div]} {THEORY_SUBJ[subj]['name']}: "
                    f"got {count}, need {expected}")

    # HC2 – Fluctuation
    for div in range(NUM_DIVS):
        counts = {_get_val(solver, div_day_hours[(div, d)]) for d in range(NUM_DAYS)}
        if len(counts) == 1:
            violations.append(f"HC2 – {DIVISIONS[div]}: all days have same hour count ({list(counts)[0]})")

    # HC3/HC4 – Break slot (implicit, always enforced by variable structure)

    # HC7 – Lab room double-booking
    for day in range(NUM_DAYS):
        for slot in ACADEMIC_SLOTS:
            for r in range(NUM_LABS):
                users = [
                    (b, ls, ss)
                    for b in range(NUM_BATCHES)
                    for ls in range(NUM_LAB_SUBJ)
                    for ss in LAB_START_SLOTS
                    if (ss == slot or ss + 1 == slot)
                    and _get_val(solver, lr[(b, ls, day, ss, r)])
                ]
                if len(users) > 1:
                    violations.append(
                        f"HC7 – Lab {LABS_LIST[r]} double-booked "
                        f"{DAYS[day]} {SLOT_NAMES[slot]}: {users}")

    # HC8 – Teacher clash (all labs now treated uniformly — CMPM-Lab sibling pairs
    # have different teachers so no special exemption needed)
    for teacher in sorted({t for s in THEORY_SUBJ for t in s['teachers'].values()} |
                          {t for s in LAB_SUBJ for t in s['teachers'].values()}):
        for day in range(NUM_DAYS):
            for slot in ACADEMIC_SLOTS:
                cnt = 0
                for div in range(NUM_DIVS):
                    for subj in range(NUM_THEORY_SUBJ):
                        if THEORY_SUBJ[subj]['teachers'].get(div) == teacher:
                            cnt += _get_val(solver, tv[(div, subj, day, slot)])
                for b in range(NUM_BATCHES):
                    for ls in range(NUM_LAB_SUBJ):
                        if LAB_SUBJ[ls]['teachers'].get(b) == teacher:
                            for ss in LAB_START_SLOTS:
                                if ss == slot or ss + 1 == slot:
                                    cnt += _get_val(solver, lv[(b, ls, day, ss)])
                if cnt > 1:
                    violations.append(
                        f"HC8 – Teacher {teacher} clash: "
                        f"{DAYS[day]} {SLOT_NAMES[slot]} (count={cnt})")


    # HC16/HC17 – OE pattern
    oe1_days = [d for d in range(NUM_DAYS) if _get_val(solver, oe1[d])]
    oe2_days = [d for d in range(NUM_DAYS) if _get_val(solver, oe2[d])]
    if len(oe1_days) != 1:
        violations.append(f"HC16 – Expected 1 OE-1hr day, got {oe1_days}")
    if len(oe2_days) != 1:
        violations.append(f"HC16 – Expected 1 OE-2hr day, got {oe2_days}")
    if oe1_days and oe2_days and oe1_days[0] == oe2_days[0]:
        violations.append(f"HC16 – OE-1hr and OE-2hr on same day ({oe1_days[0]})")

    # HC17 – WE-Lab twice per week
    for b in range(NUM_BATCHES):
        cnt = sum(_get_val(solver, lv[(b, WE_LAB_IDX, d, ss)])
                  for d in range(NUM_DAYS) for ss in LAB_START_SLOTS)
        if cnt != 2:
            violations.append(f"HC17 – {BATCHES[b]} WE-Lab: {cnt} sessions (need 2)")
        we_days = [d for d in range(NUM_DAYS)
                   if any(_get_val(solver, lv[(b, WE_LAB_IDX, d, ss)])
                          for ss in LAB_START_SLOTS)]
        if len(we_days) != len(set(we_days)):
            violations.append(f"HC17 – {BATCHES[b]} WE-Lab on same day twice")

    # HC18 – Other labs exactly once
    for b in range(NUM_BATCHES):
        for ls in range(NUM_LAB_SUBJ):
            if ls == WE_LAB_IDX:
                continue
            cnt = sum(_get_val(solver, lv[(b, ls, d, ss)])
                      for d in range(NUM_DAYS) for ss in LAB_START_SLOTS)
            if cnt != 1:
                violations.append(
                    f"HC18 – {BATCHES[b]} {LAB_SUBJ[ls]['name']}: {cnt} sessions (need 1)")


    # HC13 – Sibling sync for non-CMPM labs REMOVED from model, so no check here.

    # HC14 – CMPM-Lab sibling pairs must start simultaneously
    from data import SIBLING_PAIRS
    for (b1, b2) in SIBLING_PAIRS:
        for day in range(NUM_DAYS):
            for ss in LAB_START_SLOTS:
                v1 = _get_val(solver, lv[(b1, CMPM_LAB_IDX, day, ss)])
                v2 = _get_val(solver, lv[(b2, CMPM_LAB_IDX, day, ss)])
                if v1 != v2:
                    violations.append(
                        f"HC14 – CMPM-Lab {BATCHES[b1]}/{BATCHES[b2]} desync "
                        f"{DAYS[day]} {SLOT_NAMES[ss]}: {v1} vs {v2}")


    return violations


# ---------------------------------------------------------------------------
# Print division timetable grid
# ---------------------------------------------------------------------------

def _print_div_timetable(solver, tv, oe1, oe2, lv, lr, is_break, div):
    oe1_day = next((d for d in range(NUM_DAYS) if _get_val(solver, oe1[d])), None)
    oe2_day = next((d for d in range(NUM_DAYS) if _get_val(solver, oe2[d])), None)

    div_name = DIVISIONS[div]
    classroom = CLASSROOMS[div]
    batches   = DIV_TO_BATCHES[div]

    print(f"\n{'='*80}")
    print(f"  TIMETABLE — Division {div_name}   (Classroom: {classroom})")
    print(f"{'='*80}")

    cols = 1 + NUM_DAYS
    print(_hline(cols))
    print(_row(['Slot'] + DAYS))
    print(_hline(cols))

    for slot in range(NUM_SLOTS):
        sname = SLOT_NAMES[slot]

        row_cells = [sname]
        for day in range(NUM_DAYS):
            cell_text = ''
            # Break check
            if _get_val(solver, is_break[(div, day, slot)]):
                cell_text = '--- BREAK ---'
            # OE check
            elif day == oe2_day and slot in (0, 1):
                cell_text = 'OE(2hr)'
            elif day == oe1_day and slot == 0:
                cell_text = 'OE(1hr)'
            else:
                # Theory?
                for subj in range(NUM_THEORY_SUBJ):
                    if _get_val(solver, tv[(div, subj, day, slot)]):
                        teacher = THEORY_SUBJ[subj]['teachers'][div]
                        cell_text = f"{THEORY_SUBJ[subj]['name']}({teacher})"
                        break
                # Lab (use first batch as representative)?
                if not cell_text:
                    b_rep = batches[0]
                    for ls in range(NUM_LAB_SUBJ):
                        for ss in LAB_START_SLOTS:
                            if (ss == slot or ss + 1 == slot) and \
                               _get_val(solver, lv[(b_rep, ls, day, ss)]):
                                room = next(
                                    (LABS_LIST[r] for r in range(NUM_LABS)
                                     if _get_val(solver, lr[(b_rep, ls, day, ss, r)])), '?')
                                lname = LAB_SUBJ[ls]['name']
                                suffix = '' if ss == slot else '(c)'
                                cell_text = f"{lname}{suffix}"

            row_cells.append(cell_text if cell_text else '.')
        print(_row(row_cells))

    print(_hline(cols))


# ---------------------------------------------------------------------------
# Print batch lab timetable
# ---------------------------------------------------------------------------

def _print_batch_timetables(solver, lv, lr):
    print(f"\n{'='*80}")
    print("  BATCH LAB TIMETABLES")
    print(f"{'='*80}")
    for b in range(NUM_BATCHES):
        print(f"\n  Batch {BATCHES[b]}:")
        print(f"  {'Day':<12} {'Slot':<6} {'Lab':<12} {'Teacher':<8} {'Room'}")
        print(f"  {'-'*55}")
        for day in range(NUM_DAYS):
            for ls in range(NUM_LAB_SUBJ):
                for ss in LAB_START_SLOTS:
                    if _get_val(solver, lv[(b, ls, day, ss)]):
                        teacher = LAB_SUBJ[ls]['teachers'][b]
                        room = next(
                            (LABS_LIST[r] for r in range(NUM_LABS)
                             if _get_val(solver, lr[(b, ls, day, ss, r)])), '?')
                        print(f"  {DAYS[day]:<12} {SLOT_NAMES[ss]:<6} "
                              f"{LAB_SUBJ[ls]['name']:<12} {teacher:<8} {room}")


# ---------------------------------------------------------------------------
# Main report function
# ---------------------------------------------------------------------------

def solve_and_report(model, vars_dict):
    solver  = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = 90   # 90s: enough to reach penalty=145 (proven optimal)

    tv            = vars_dict['tv']
    oe1           = vars_dict['oe1']
    oe2           = vars_dict['oe2']
    lv            = vars_dict['lv']
    lr            = vars_dict['lr']
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
        
        # --- Multi-Objective Scores ---
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


        # --- Hard constraint check ---
        print("\n--- HARD CONSTRAINT VIOLATIONS (target: 0) ---")
        violations = check_hard_violations(solver, tv, oe1, oe2, lv, lr, div_day_hours)
        if violations:
            for v in violations:
                print(f"  [FAIL]  {v}")
        else:
            print("  [OK]  No hard violations detected.")
        print(f"  Total hard violations: {len(violations)}")

        # --- Daily hours summary ---
        print("\n--- DAILY ACADEMIC HOURS PER DIVISION ---")
        print(f"  {'':8}", end='')
        for d in DAYS:
            print(f"{d:>6}", end='')
        print()
        for div in range(NUM_DIVS):
            print(f"  {DIVISIONS[div]:8}", end='')
            for day in range(NUM_DAYS):
                h = solver.Value(div_day_hours[(div, day)])
                print(f"{h:>6}", end='')
            print()

        # --- OE schedule ---
        oe1_day = next((d for d in range(NUM_DAYS) if solver.Value(oe1[d])), None)
        oe2_day = next((d for d in range(NUM_DAYS) if solver.Value(oe2[d])), None)
        print(f"\n  OE 1-hr  : {DAYS[oe1_day] if oe1_day is not None else 'NONE'} @ H1")
        print(f"  OE 2-hr  : {DAYS[oe2_day] if oe2_day is not None else 'NONE'} @ H1-H2")

        # --- Division timetables ---
        is_break = vars_dict['is_break']
        for div in range(NUM_DIVS):
            _print_div_timetable(solver, tv, oe1, oe2, lv, lr, is_break, div)

        # --- Batch lab timetables ---
        _print_batch_timetables(solver, lv, lr)

    elif status == cp_model.INFEASIBLE:
        print("\n  *** MODEL IS INFEASIBLE ***")
        print("  The solver proved no feasible solution exists under the given constraints.")
        print("\n  Likely conflicting constraint groups:")
        print("   • HC14 (CMPM-Lab sibling simultaneous) + HC8 (teacher clash for AVG)")
        print("     → AVG is the teacher for both B1 and B2 CMPM-Lab; forcing simultaneity")
        print("       means AVG must supervise two rooms at once.")
        print("   • HC2  (fluctuation) + HC1 (daily hours 5-8) + fixed session totals")
        print("     → Total weekly sessions = 30/div, min 5/day forces near-uniform distribution.")
        print("\n  Tip: Run with model.Validate() output (printed at end of main.py) for details.")
        print("  Tip: Relax HC14 to a soft constraint to regain feasibility.")

    else:
        print(f"\n  Solver returned status: {status_name}")

    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80 + "\n")
    
    return solver, status, vars_dict
