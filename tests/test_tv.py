import itertools

import pytest

from tv import TV, tv_and, tv_not, tv_or

T, F, U = TV.T, TV.F, TV.U

AND = {(T, T): T, (T, F): F, (T, U): U,
       (F, T): F, (F, F): F, (F, U): F,
       (U, T): U, (U, F): F, (U, U): U}
OR = {(T, T): T, (T, F): T, (T, U): T,
      (F, T): T, (F, F): F, (F, U): U,
      (U, T): T, (U, F): U, (U, U): U}


@pytest.mark.parametrize("pair,want", list(sorted(AND.items(), key=str)))
def test_and_table(pair, want):
    assert tv_and(*pair) is want


@pytest.mark.parametrize("pair,want", list(sorted(OR.items(), key=str)))
def test_or_table(pair, want):
    assert tv_or(*pair) is want


@pytest.mark.parametrize("a,want", [(T, F), (F, T), (U, U)])
def test_not_table(a, want):
    assert tv_not(a) is want


@pytest.mark.parametrize("a,b", list(itertools.product([T, F, U], repeat=2)))
def test_de_morgan(a, b):
    assert tv_not(tv_and(a, b)) is tv_or(tv_not(a), tv_not(b))


@pytest.mark.parametrize("a", [T, F, U])
def test_double_negation(a):
    assert tv_not(tv_not(a)) is a


def test_false_short_circuits_unknown():
    assert tv_and(F, U) is F


def test_true_short_circuits_unknown():
    assert tv_or(T, U) is T


def test_and_flattens_lists():
    assert tv_and([T, T, [T, F]]) is F


def test_or_flattens_lists():
    assert tv_or([F, F, [F, T]]) is T


def test_empty_and_is_true():
    assert tv_and([]) is T


def test_empty_or_is_false():
    assert tv_or([]) is F


def test_of_none_is_unknown():
    assert TV.of(None) is U


@pytest.mark.parametrize("v,want", [(1, T), (0, F), ("x", T), ("", F), (True, T), (False, F)])
def test_of_python_values(v, want):
    assert TV.of(v) is want


def test_bool_is_refused():
    # U 가 조용히 F 가 되는 것을 막는다
    with pytest.raises(TypeError):
        bool(U)
