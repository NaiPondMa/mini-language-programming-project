import pytest

from lumi import run
from lumi.errors import LumiRuntimeError
from lumi.evaluator import Interpreter


def value(src):
    """Value of the last statement."""
    return Interpreter(out=lambda _: None).run(src)


def test_arithmetic():
    assert value("1 + 2 * 3") == 7
    assert value("7 / 2") == 3
    assert value("7.0 / 2") == 3.5
    assert value("7 % 3") == 1
    assert value("-(2 + 3)") == -5


def test_comparison_and_booleans():
    assert value("1 < 2 && 2 < 3") is True
    assert value("1 == 1 || 1 / 0 == 0") is True  # || short-circuits
    assert value("not (1 == 2)") is True
    assert value("true == 1") is False             # bool is not int in Lumi


def test_strings_and_lists():
    assert value('"ab" ++ "cd"') == "abcd"
    assert value("[1, 2] ++ [3]") == [1, 2, 3]
    assert value("0 :: [1]") == [0, 1]
    assert value("length [1, 2, 3]") == 3


def test_closures_capture_their_environment():
    assert value("let make n = fn x => x + n\nlet add5 = make 5\nadd5 10") == 15


def test_currying_and_partial_builtins():
    assert value("let add a b = a + b\nlet inc = add 1\ninc 41") == 42
    assert value("let double = map (fn x => x * 2)\ndouble [1, 2]") == [2, 4]


def test_let_rec_and_tail_calls():
    assert value("let rec f n = if n == 0 then 1 else n * f (n - 1)\nf 10") == 3628800
    # a deep tail-recursive loop must not overflow the Python stack
    assert value("let rec loop n = if n == 0 then 0 else loop (n - 1)\nloop 50000") == 0


def test_local_let_rec():
    src = "let rec go n acc = if n == 0 then acc else go (n - 1) (acc + n) in go 10 0"
    assert value(src) == 55


def test_pattern_matching():
    src = """
let rec sum xs = match xs with
  | [] -> 0
  | h :: t -> h + sum t
sum [1, 2, 3, 4]
"""
    assert value(src) == 10
    assert value("match (1, 2) with | (a, b) -> a + b") == 3
    assert value("match [1, 2] with | [a, b] -> b | _ -> 0") == 2
    assert value("match 'red with | 'blue -> 1 | 'red -> 2") == 2


def test_pipe():
    assert value("[1, 2, 3] |> map (fn x => x + 1) |> sum") == 9


def test_fold_and_filter():
    assert value("fold (fn a x => a * x) 1 [1, 2, 3, 4]") == 24
    assert value("filter (fn x => x > 2) [1, 2, 3, 4]") == [3, 4]


def test_print_output():
    assert run('print "hi"\nprint [1, "a"]\nprint (1, true)') == ['hi', '[1, "a"]', '(1, true)']


@pytest.mark.parametrize("src, fragment", [
    ('1 + "a"', "use ++"),
    ("1 / 0", "division by zero"),
    ("prnt 1", "did you mean 'print'"),
    ("match 3 with | 1 -> 0", "no pattern matched"),
    ("if 1 then 2 else 3", "must be a bool"),
    ("head []", "empty list"),
    ("5 6", "cannot call int"),
])
def test_runtime_errors(src, fragment):
    with pytest.raises(LumiRuntimeError) as info:
        value(src)
    assert fragment in info.value.message
    assert info.value.pos is not None
