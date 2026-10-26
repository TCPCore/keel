import pytest

from keel.attribution import (
    Unit,
    compose_curve,
    greedy_select,
    layer_histogram,
    null_reduction,
    screen,
)


def test_unit_key_roundtrip():
    unit = Unit(3, 7)
    assert unit.key == "L03.0007"
    assert Unit.parse(unit.key) == unit
    assert Unit.parse("3.7") == unit
    with pytest.raises(ValueError):
        Unit.parse("nope")


def test_screen_orders_by_score_and_truncates():
    effects = [(Unit(0, i), float(i) / 10) for i in range(10)]
    top = screen(effects, top_n=3)
    assert [s.unit.index for s in top] == [9, 8, 7]


def test_screen_blends_lens():
    effects = [(Unit(0, 0), 1.0), (Unit(0, 1), 1.0)]
    top = screen(effects, lens={Unit(0, 1): 3.0}, top_n=2)
    assert top[0].unit.index == 1


def test_greedy_finds_the_planted_unit():
    truth = Unit(2, 5)

    def evaluate(units):
        return 0.0 if truth in units else 1.0

    selection = greedy_select(
        [Unit(0, i) for i in range(5)] + [truth], evaluate, k=3, epsilon=0.01
    )
    assert selection.units == [truth]
    assert selection.final == 0.0
    # 1 baseline + 6 in round one + 5 in round two before the improvement
    # falls below epsilon and the search stops.
    assert selection.evaluations == 1 + 6 + 5


def test_greedy_stops_when_improvement_is_negligible():
    selection = greedy_select(
        [Unit(0, 0), Unit(0, 1)], lambda units: 1.0, k=3, epsilon=0.01
    )
    assert selection.units == []
    assert selection.curve == [1.0]


def test_null_reduction_is_not_the_signal():
    truth = {Unit(2, i) for i in range(3)}

    def evaluate(units):
        return float(len(truth - set(units)))

    null_mean, null_sd = null_reduction(
        [Unit(0, i) for i in range(50)], evaluate, k=3, trials=16, seed=0
    )
    assert null_sd >= 0.0
    selection = greedy_select(sorted(truth), evaluate, k=3)
    assert selection.final == 0.0
    assert null_mean < 3.0


def test_compose_curve_clamps_to_available_units():
    units = [Unit(0, i) for i in range(10)]
    curve = compose_curve(units, lambda s: float(len(s)), sizes=(1, 4, 20))
    assert curve == [(1, 1.0), (4, 4.0), (10, 10.0)]


def test_layer_histogram():
    hist = layer_histogram([Unit(1, 0), Unit(1, 1), Unit(3, 9)])
    assert hist == {1: 2, 3: 1}
