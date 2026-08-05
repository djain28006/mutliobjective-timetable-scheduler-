"""
data.py — Static input data for the University Timetable Scheduling System.
All divisions, batches, teachers, subjects, rooms, and constraint parameters.
"""

# =============================================================================
# TIME STRUCTURE
# =============================================================================
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
NUM_DAYS = 5

# Slot indices: 0=H1, 1=H2, 2=H3, 3=H4, 4=H5, 5=H6, 6=H7, 7=H8, 8=H9
SLOT_NAMES = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9']
NUM_SLOTS  = 9
ACADEMIC_SLOTS = [s for s in range(NUM_SLOTS)]  # [0,1,2,3,4,5,6,7,8]

# Valid lab start slots: s where both s and s+1 are academic
LAB_START_SLOTS = [s for s in ACADEMIC_SLOTS if (s + 1) in ACADEMIC_SLOTS]

# Morning / afternoon academic blocks (for consecutive-check soft constraints)
MORNING_SLOTS   = [0, 1, 2, 3]
AFTERNOON_SLOTS = [5, 6, 7, 8]
LAST_SLOT       = 8   # H9

# =============================================================================
# DIVISIONS & BATCHES
# =============================================================================
DIVISIONS   = ['D1', 'D2', 'D3']
NUM_DIVS    = 3

BATCHES     = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6']
NUM_BATCHES = 6

BATCH_TO_DIV  = [0, 0, 1, 1, 2, 2]           # batch_idx -> div_idx
DIV_TO_BATCHES = [[0, 1], [2, 3], [4, 5]]    # div_idx   -> [batch_idx, ...]
SIBLING_PAIRS  = [(0, 1), (2, 3), (4, 5)]    # (B1,B2), (B3,B4), (B5,B6)

# =============================================================================
# ROOMS
# =============================================================================
CLASSROOMS    = ['Class-D1', 'Class-D2', 'Class-D3']   # dedicated one per division
NUM_CLASSROOMS = 3

LABS_LIST = ['Lab-1', 'Lab-2', 'Lab-3', 'Lab-4']
NUM_LABS  = 4

# =============================================================================
# THEORY SUBJECTS   (index 0..4)
# =============================================================================
# teachers: div_idx -> teacher_name
THEORY_SUBJ = [
    {'name': 'DS',   'weekly': 4, 'teachers': {0: 'NM',  1: 'RP',  2: 'SAM'}},
    {'name': 'ML-I', 'weekly': 3, 'teachers': {0: 'KRS', 1: 'SSM', 2: 'KRS'}},
    {'name': 'SDS',  'weekly': 2, 'teachers': {0: 'AB',  1: 'MA',  2: 'NP'}},
    {'name': 'EFM',  'weekly': 2, 'teachers': {0: 'PT',  1: 'AG',  2: 'AG'}},
    {'name': 'CMPM', 'weekly': 2, 'teachers': {0: 'AVG', 1: 'MAA', 2: 'RP'}},
]
NUM_THEORY_SUBJ = len(THEORY_SUBJ)

# OE is teacher-free and handled separately via oe1/oe2 day variables.
# Pattern: exactly one 1-hr session on one day (H1 only)
#          exactly one 2-hr session on a different day (H1+H2)

# =============================================================================
# LAB SUBJECTS   (index 0..5)
# =============================================================================
# teachers: batch_idx -> teacher_name
WE_LAB_IDX   = 3    # WE-Lab is scheduled TWICE per week per batch
CMPM_LAB_IDX = 5    # CMPM-Lab has the special simultaneous sibling constraint

LAB_SUBJ = [
    {   # 0 – DS-Lab
        'name': 'DS-Lab', 'twice': False, 'is_cmpm_lab': False,
        'teachers': {0:'NM', 1:'NM', 2:'RP', 3:'RP', 4:'SAM', 5:'SAM'},
    },
    {   # 1 – ML-Lab
        'name': 'ML-Lab', 'twice': False, 'is_cmpm_lab': False,
        'teachers': {0:'KRS', 1:'KRS', 2:'SSM', 3:'SSM', 4:'KRS', 5:'KRS'},
    },
    {   # 2 – SDS-Lab
        'name': 'SDS-Lab', 'twice': False, 'is_cmpm_lab': False,
        'teachers': {0:'AB', 1:'AB', 2:'MA', 3:'MA', 4:'NP', 5:'NP'},
    },
    {   # 3 – WE-Lab  (GW teaches ALL batches; siblings never do WE-Lab simultaneously
        #              because HC13 allows different labs for the sibling — GW clash avoided)
        'name': 'WE-Lab', 'twice': True, 'is_cmpm_lab': False,
        'teachers': {0:'GW', 1:'GW', 2:'GW', 3:'GW', 4:'GW', 5:'GW'},
    },
    {   # 4 – PBC-Lab
        'name': 'PBC-Lab', 'twice': False, 'is_cmpm_lab': False,
        'teachers': {0:'KT', 1:'KT', 2:'KT', 3:'KT', 4:'RVP', 5:'RVP'},
    },
    {   # 5 – CMPM-Lab
        # Each sibling pair has DIFFERENT teachers so HC14 (simultaneous start)
        # no longer causes a teacher clash:
        #   D1: B1→AVG, B2→MAA   |   D2: B3→MAA, B4→AVG   |   D3: B5→RP, B6→AVG
        'name': 'CMPM-Lab', 'twice': False, 'is_cmpm_lab': True,
        'teachers': {0:'AVG', 1:'MAA', 2:'MAA', 3:'AVG', 4:'RP', 5:'AVG'},
    },
]
NUM_LAB_SUBJ = len(LAB_SUBJ)

# =============================================================================
# TEACHER REGISTRY
# =============================================================================
ALL_TEACHERS = sorted({
    t for s in THEORY_SUBJ for t in s['teachers'].values()
} | {
    t for s in LAB_SUBJ for t in s['teachers'].values()
})
# OE teachers (OE-T1/T2/T3) are excluded — OE is teacher-free per user specification.

# =============================================================================
# THEORY ↔ LAB SUBJECT PAIRS  (HC21: same-subject theory-lab no overlap)
# =============================================================================
THEORY_LAB_PAIRS = [
    (0, 0),   # DS    <->  DS-Lab
    (1, 1),   # ML-I  <->  ML-Lab
    (2, 2),   # SDS   <->  SDS-Lab
    (4, 5),   # CMPM  <->  CMPM-Lab
]

# =============================================================================
# DAILY HOUR CONSTRAINTS
# =============================================================================
# NOTE: With total weekly sessions = 16 theory + 14 lab = 30 per division,
# strict [6,8] forces every day = 6 with no fluctuation possible.
# We relax lower bound to 5 so the solver can achieve fluctuation (e.g. 5-7 range).
MIN_HOURS_PER_DAY = 5
MAX_HOURS_PER_DAY = 8

# =============================================================================
# DIFFICULT SUBJECTS  (for S4 soft constraint)
# =============================================================================
DIFFICULT_SUBJ_IDX = {0, 1, 4}   # DS, ML-I, CMPM

# =============================================================================
# SOFT CONSTRAINT WEIGHTS
# =============================================================================
# FACULTY SCORE WEIGHTS
# =============================================================================
W_FAC_GAP        = 8    # Teacher idle gap between sessions
W_FAC_OVERLOAD   = 5    # Penalty for each hour > 4 hours/day (reduced from 50)
W_FAC_H1         = 5    # Teacher assigned to slot H1
W_FAC_H9         = 5    # Teacher assigned to slot H9
W_FAC_CONSEC     = 10   # Teacher working 3+ consecutive slots

# =============================================================================
# STUDENT SCORE WEIGHTS
# =============================================================================
W_STU_CONSEC_DIFF= 10   # 3 consecutive slots all difficult subjects
W_STU_THEORY_H9  = 5    # Theory lecture in H9 (labs allowed)
W_STU_3DAYS_SAME = 15   # Same theory subject on 3+ consecutive days
W_STU_CAMPUS_STAY= 1    # Restored to 1 to introduce conflict
# (S1, S3, S7, S9 are dropped as they are superseded by these explicit user rules)

# =============================================================================
# RESOURCE SCORE WEIGHTS
# =============================================================================
W_RES_CLASSROOM  = 5    # Uneven classroom usage (max-min)
W_RES_LAB        = 3    # Uneven lab room usage (max-min)
