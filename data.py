"""
data.py — DataBundle: the input data for the University Timetable Scheduling System,
as an explicit, parameterizable object instead of module-level globals.

DataBundle.default() holds today's hardcoded DJSCE-shaped dataset (divisions, batches,
teachers, subjects, rooms, constraint parameters) — the same values `data.py` used to
export as globals, now returned as a fresh object each call so callers can freely mutate
their own copy without affecting others.
"""

from dataclasses import dataclass


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
            # WE-Lab: GW teaches ALL batches; siblings never do WE-Lab simultaneously
            # because HC13 allows different labs for the sibling — GW clash avoided.
            {'name': 'WE-Lab', 'twice': True, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'GW', 1: 'GW', 2: 'GW', 3: 'GW', 4: 'GW', 5: 'GW'}},
            {'name': 'PBC-Lab', 'twice': False, 'sibling_sync': False, 'day_edges_only': False,
             'teachers': {0: 'KT', 1: 'KT', 2: 'KT', 3: 'KT', 4: 'RVP', 5: 'RVP'}},
            # CMPM-Lab: each sibling pair has DIFFERENT teachers so the sibling-sync
            # simultaneous-start rule doesn't cause a teacher clash:
            #   D1: B1->AVG, B2->MAA | D2: B3->MAA, B4->AVG | D3: B5->RP, B6->AVG
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
