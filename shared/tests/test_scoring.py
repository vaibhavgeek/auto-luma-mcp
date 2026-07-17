import pytest

from lumabot_shared.scoring import clamp_score, validate_score, weighted_score


def test_score_ranges() -> None:
    assert clamp_score(-10) == 0
    assert clamp_score(101.4) == 100
    assert validate_score(55) == 55

    with pytest.raises(ValueError, match="between 0 and 100"):
        validate_score(101)


def test_weighted_score() -> None:
    assert weighted_score({"fit": 80, "timing": 60}, {"fit": 0.75, "timing": 0.25}) == 75

    with pytest.raises(ValueError, match="total weight"):
        weighted_score({"fit": 80}, {"fit": 0})
