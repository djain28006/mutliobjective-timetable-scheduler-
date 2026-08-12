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
