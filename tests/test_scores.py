from app import _score_from_label

def test_score_positive():
    assert _score_from_label("positivo", 0.9) > 0
    assert _score_from_label("positivo", 0.5) < _score_from_label("positivo", 0.9)

def test_score_negative():
    assert _score_from_label("negativo", 0.9) < 0
    assert _score_from_label("negativo", 0.5) > _score_from_label("negativo", 0.9)

def test_score_neutral():
    assert _score_from_label("neutro", 0.5) == 0
