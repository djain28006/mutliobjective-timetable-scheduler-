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
