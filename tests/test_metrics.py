from src import metrics


def test_recall_and_mrr():
    assert metrics.recall_at_k(["a", "b", "c"], ["c", "z"], k=5) == 0.5
    assert metrics.mrr(["a", "b", "c"], ["b"]) == 0.5
    assert metrics.mrr(["a"], ["z"]) == 0.0


def test_keywords_match():
    assert metrics.keywords_match("Onze joueurs, gardien compris", [["onze", "11"], ["gardien"]])
    assert not metrics.keywords_match("dix joueurs", [["onze", "11"]])


def test_pass_hat_k():
    assert metrics.pass_hat_k([True, True, True])
    assert not metrics.pass_hat_k([True, False, True])


def test_numbers_match_whole():
    assert metrics.keywords_match("6 tirs cadrés", [["6"]])
    assert not metrics.keywords_match("16 tirs en 2026", [["6"]])
    assert not metrics.keywords_match("6,5 tirs", [["6"]])
    assert metrics.keywords_match("à 16,5 m des poteaux.", [["16,5"]])
    assert metrics.keywords_match("score 3-3.", [["3-3"]])
    assert not metrics.keywords_match("à 11 m du but", [["1 m"]])
    assert metrics.keywords_match("à 1 m du mur", [["1 m"]])
    assert metrics.keywords_match("Onze joueurs", [["onze"]])


def test_bootstrap_ci():
    lo, hi = metrics.bootstrap_ci([1, 1, 0, 1, 0, 1, 1, 1], seed=1)
    assert 0 <= lo <= 0.75 <= hi <= 1
    assert metrics.bootstrap_ci([1]) is None
    assert metrics.bootstrap_ci([1, 1, 1]) == (1.0, 1.0)


def test_paired_bootstrap():
    r = metrics.paired_bootstrap([0] * 10, [1] * 10)
    assert r["diff"] == 1 and r["lo"] == r["hi"] == 1 and r["p_le_0"] == 0
    assert metrics.paired_bootstrap([1, 0], [1, 0])["p_le_0"] == 1


def test_errors_excluded_from_quality_metrics():
    import eval as ev

    rows = [{"id": "d1", "type": "doc", "trial": 0, "correct": True},
            {"id": "d2", "type": "doc", "trial": 0, "correct": False, "error": "429"},
            {"id": "t1", "type": "task", "trial": 0, "correct": True},
            {"id": "t1", "type": "task", "trial": 1, "correct": True, "error": "429"},
            {"id": "t1", "type": "task", "trial": 2, "correct": True}]
    lists = ev.metric_lists(1, rows)
    assert lists["Exactitude"] == [True] and lists["pass^3"] == []


def test_unsupported_numbers_accepts_probability_as_percentage():
    outputs = ['{"probabilities": {"home_win": 0.186, "draw": 0.234}, "shots": 9}']
    assert metrics.unsupported_numbers("Victoire 18,6 %, nul 23 %, 9 tirs.", outputs) == []
    assert metrics.unsupported_numbers("Victoire 31 %, 112 kilomètres.", outputs) == [31.0, 112.0]
