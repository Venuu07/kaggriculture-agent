"""Verified reflection proposes evidence-based lessons tied to concrete strategy changes."""
from kagri.reflection import HYPOTHESES, NOVICE


def test_novice_gets_investment_hypotheses():
    ev = {"profit": 50000, "sales": {"MELON": {"units": 60, "avg_price": 90.0, "base": 250}},
          "max_weeds": 2}
    out = {hid: fn(dict(NOVICE), ev) for hid, fn in HYPOTHESES}
    assert out["animals"][1]["allow_animals"] is True
    assert out["land"][1]["allow_land"] is True
    assert out["glut"][1]["bias_MELON"] < 1.0 and "Melon" in out["glut"][0]
    assert out["labour"] is None  # few weeds -> no labour lesson
