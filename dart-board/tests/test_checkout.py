from src.dart_board.checkout import suggest_checkout


def test_170_has_classic_finish():
    combos = suggest_checkout(170)
    assert ["T20", "T20", "DB"] in combos


def test_40_can_finish_single_dart():
    combos = suggest_checkout(40)
    assert ["D20"] in combos


def test_unfinishable_score_returns_empty():
    assert suggest_checkout(169) == []
