"""Built-in functions available in every Lumi program.

To add a new built-in, write a Python function and decorate it with
@builtin("name", arity). Built-ins are curried automatically, so
`map f` (one argument short) returns a partially applied function.
"""

from .errors import LumiRuntimeError
from .values import UNIT, Builtin, is_number, show, type_name


def _want(cond, fn_name, expected, value):
    if not cond:
        raise LumiRuntimeError(
            f"{fn_name} expects {expected}, got {type_name(value)} {show(value)}")


def _want_bool(fn_name, value):
    _want(isinstance(value, bool), fn_name, "a function returning bool", value)
    return value


def make_builtins(interp):
    table = {}

    def builtin(name, arity):
        def register(fn):
            table[name] = Builtin(name, arity, fn)
            return fn
        return register

    @builtin("print", 1)
    def _print(v):
        interp.out(show(v, top=True))
        return UNIT

    @builtin("str", 1)
    def _str(v):
        return show(v, top=True)

    @builtin("length", 1)
    def _length(xs):
        _want(isinstance(xs, (list, str, tuple)), "length", "a list or string", xs)
        return len(xs)

    @builtin("head", 1)
    def _head(xs):
        _want(isinstance(xs, list), "head", "a list", xs)
        if not xs:
            raise LumiRuntimeError("head of an empty list")
        return xs[0]

    @builtin("tail", 1)
    def _tail(xs):
        _want(isinstance(xs, list), "tail", "a list", xs)
        if not xs:
            raise LumiRuntimeError("tail of an empty list")
        return xs[1:]

    @builtin("empty", 1)
    def _empty(xs):
        _want(isinstance(xs, (list, str)), "empty", "a list or string", xs)
        return len(xs) == 0

    @builtin("map", 2)
    def _map(f, xs):
        _want(isinstance(xs, list), "map", "a list as 2nd argument", xs)
        return [interp.apply(f, x) for x in xs]

    @builtin("filter", 2)
    def _filter(f, xs):
        _want(isinstance(xs, list), "filter", "a list as 2nd argument", xs)
        return [x for x in xs if _want_bool("filter", interp.apply(f, x))]

    @builtin("fold", 3)
    def _fold(f, acc, xs):
        _want(isinstance(xs, list), "fold", "a list as 3rd argument", xs)
        for x in xs:
            acc = interp.apply(interp.apply(f, acc), x)
        return acc

    @builtin("range", 2)
    def _range(a, b):
        _want(isinstance(a, int) and not isinstance(a, bool), "range", "an int", a)
        _want(isinstance(b, int) and not isinstance(b, bool), "range", "an int", b)
        return list(range(a, b))

    @builtin("reverse", 1)
    def _reverse(xs):
        _want(isinstance(xs, (list, str)), "reverse", "a list or string", xs)
        return xs[::-1]

    @builtin("sum", 1)
    def _sum(xs):
        _want(isinstance(xs, list) and all(is_number(x) for x in xs),
              "sum", "a list of numbers", xs)
        return sum(xs)

    @builtin("not", 1)
    def _not(b):
        _want(isinstance(b, bool), "not", "a bool", b)
        return not b

    @builtin("max", 2)
    def _max(a, b):
        _want(is_number(a) and is_number(b), "max", "two numbers", (a, b))
        return max(a, b)

    @builtin("min", 2)
    def _min(a, b):
        _want(is_number(a) and is_number(b), "min", "two numbers", (a, b))
        return min(a, b)

    return table
