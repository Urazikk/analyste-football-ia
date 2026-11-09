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
