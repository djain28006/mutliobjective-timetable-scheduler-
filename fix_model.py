with open('model.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, l in enumerate(lines):
    if 'Pre-build active slots per division to compute campus stay and idle gaps' in l:
        if skip:
            pass
        else:
            skip = True
            new_lines.append('''    # Pre-build active slots per division to compute campus stay and idle gaps
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

                # No theory or lab during break
                model.Add(act_s == 0).OnlyEnforceIf(is_break[(div, day, s)])
                
                # Active physical + break = is_on_campus (for the block)
                model.Add(is_on_campus[(div, day, s)] == act_s + is_break[(div, day, s)])
            
            # Campus total size = active slots + 1 break
            model.Add(sum(is_on_campus[(div, day, s)] for s in range(9)) == div_day_hours[(div, day)] + 1)
            
            # ST1: HARD CONSTRAINT: Student No-Gap
            # is_on_campus must be a single contiguous block of 1s
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
                    
                # If slot is inactive, either all before is empty or all after is empty
                model.AddBoolOr([is_on_campus[(div, day, s)], before_empty, after_empty])
''')
        continue

    if skip and '# ST2: >2 consecutive difficult subjects' in l:
        skip = False
        new_lines.append(l)
        continue

    if 'D.  OBJECTIVE — Phase 1: Expose 3 Scores + Minimise Sum' in l:
        if skip:
            pass
        else:
            skip = True
            new_lines.append(l)
        continue

    if skip and 'total_penalty = model.NewIntVar' in l:
        skip = False
        new_lines.append(l)
        continue
        
    if not skip:
        new_lines.append(l)

final_lines = []
for l in new_lines:
    if "'oe2': oe2," in l:
        final_lines.append(l)
        final_lines.append("        'is_break': is_break,\n")
    else:
        final_lines.append(l)

with open('model.py', 'w') as f:
    f.writelines(final_lines)
