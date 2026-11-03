"""Runtime values of the functional side of Lumi, and how to display them.

    Lumi value      Python representation
    ----------      ---------------------
    42, 3.5         int, float
    true            bool
    "hi"            str
    [1, 2]          list
    (1, "a")        tuple
    ()              UNIT
    fn x => ...     Closure
    print           Builtin
    'bob            logic.Struct (atom)
    {X: bob}        Record   (one answer from `solve`)
"""

from dataclasses import dataclass, field

from .logic import Struct, Var, format_term


class Unit:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "()"


UNIT = Unit()


@dataclass(eq=False)
class Closure:
    param: str
    body: object
    env: object
    name: str = None


@dataclass(eq=False)
class Builtin:
    name: str
    arity: int
    fn: object
    args: tuple = ()


@dataclass
class Record:
    fields: dict = field(default_factory=dict)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def type_name(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, tuple):
        return "tuple"
    if isinstance(v, (Closure, Builtin)):
        return "function"
    if isinstance(v, Struct):
        return "atom" if not v.args else "term"
    if isinstance(v, Record):
        return "record"
    if v is UNIT:
        return "unit"
    if isinstance(v, Var):
        return "unbound variable"
    return type(v).__name__


def show(v, top=False):
    """Turn a value into text. `top=True` prints strings without quotes."""
    if isinstance(v, str):
        return v if top else format_term(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(show(x) for x in v) + "]"
    if isinstance(v, tuple):
        return "(" + ", ".join(show(x) for x in v) + ")"
    if isinstance(v, Closure):
        return f"<fn {v.name}>" if v.name else "<fn>"
    if isinstance(v, Builtin):
        return f"<builtin {v.name}>"
    if isinstance(v, Record):
        return "{" + ", ".join(f"{k}: {show(x)}" for k, x in v.fields.items()) + "}"
    if isinstance(v, (Struct, Var)):
        return format_term(v)
    return repr(v)


def values_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, list) and isinstance(b, list) or isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, Record) and isinstance(b, Record):
        return (a.fields.keys() == b.fields.keys()
                and all(values_equal(a.fields[k], b.fields[k]) for k in a.fields))
    if isinstance(a, (Closure, Builtin)) or isinstance(b, (Closure, Builtin)):
        return a is b
    return type(a) is type(b) and a == b
