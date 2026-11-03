import pytest

from lumi import run
from lumi.errors import LumiRuntimeError
from lumi.evaluator import Interpreter
from lumi.logic import NIL, Struct, Var, make_list, resolve, unify


# ------------------------------------------------------------ unification

def test_unify_atoms():
    assert unify(Struct("a"), Struct("a"), {}) == {}
    assert unify(Struct("a"), Struct("b"), {}) is None


def test_unify_binds_variables():
    x = Var("X")
    s = unify(Struct("f", (x, Struct("b"))), Struct("f", (Struct("a"), Struct("b"))), {})
    assert resolve(x, s) == Struct("a")


def test_unify_two_ways():
    x, y = Var("X"), Var("Y")
    s = unify(Struct("p", (x, Struct("b"))), Struct("p", (Struct("a"), y)), {})
    assert resolve(x, s) == Struct("a") and resolve(y, s) == Struct("b")


def test_occurs_check():
    x = Var("X")
    assert unify(x, Struct("f", (x,)), {}) is None


def test_unify_lists():
    h, t = Var("H"), Var("T")
    s = unify(make_list([h], t), make_list([1, 2, 3]), {})
    assert resolve(h, s) == 1
    assert resolve(t, s) == make_list([2, 3])
    assert unify(NIL, make_list([1]), {}) is None


def test_numbers_must_match_type():
    assert unify(1, 1, {}) == {}
    assert unify(1, 2, {}) is None


# ------------------------------------------------------------ queries

FAMILY = """
fact parent(tom, bob).
fact parent(bob, ann).
fact parent(bob, pat).
rule grandparent(X, Z) :- parent(X, Y), parent(Y, Z).
"""


def test_query_prints_answers():
    assert run(FAMILY + "query grandparent(tom, Who)?") == ["Who = ann", "Who = pat"]


def test_query_true_and_false():
    assert run(FAMILY + "query parent(tom, bob)?\nquery parent(ann, tom)?") == ["true.", "false."]


def test_backtracking_over_several_variables():
    out = run(FAMILY + "query parent(P, C)?")
    assert out == ["P = tom, C = bob", "P = bob, C = ann", "P = bob, C = pat"]


def test_append_backwards():
    src = """
fact append([], L, L).
rule append([H|T], L, [H|R]) :- append(T, L, R).
query append(X, [3], [1, 2, 3])?
"""
    assert run(src) == ["X = [1, 2]"]


def test_arithmetic_with_is():
    src = """
fact factorial(0, 1).
rule factorial(N, F) :- N > 0, N1 is N - 1, factorial(N1, F1), F is N * F1.
query factorial(6, F)?
"""
    assert run(src) == ["F = 720"]


def test_not_unify_and_comparisons():
    assert run("query a \\= b?\nquery 3 < 2?\nquery X = f(Y), Y = 1?") == [
        "true.", "false.", "X = f(1), Y = 1"]


def test_solve_returns_records():
    out = run(FAMILY + "let rs = solve grandparent(tom, W)\nprint (map (fn r => r.W) rs)")
    assert out == ["[ann, pat]"]


def test_solve_converts_lists():
    out = run("fact nums([1, 2, 3]).\nlet r = head (solve nums(L))\nprint (sum r.L)")
    assert out == ["6"]


def test_unknown_predicate_is_an_error():
    with pytest.raises(LumiRuntimeError) as info:
        Interpreter(out=lambda _: None).run("query nope(X)?")
    assert "unknown predicate nope/1" in info.value.message


def test_unbound_arithmetic_is_an_error():
    with pytest.raises(LumiRuntimeError) as info:
        Interpreter(out=lambda _: None).run("query X is Y + 1?")
    assert "unbound" in info.value.message
