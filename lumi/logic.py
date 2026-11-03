"""The logic engine: terms, unification and SLD resolution (mini Prolog).

Terms are:
    Var            a logic variable      X, Who, _
    Struct         an atom or compound   bob, parent(tom, bob), [1, 2]
    int/float/str  plain constants

A substitution is a dict {Var: term}. Solving a query is a depth-first
search that *yields* every substitution that makes the goals true.
Python generators give us backtracking for free.
"""

import itertools
from dataclasses import dataclass

from .errors import LumiRuntimeError

_ids = itertools.count(1)


class Var:
    """A logic variable. Two Vars are the same only if they are the same object."""

    __slots__ = ("name", "id")

    def __init__(self, name="_"):
        self.name = name
        self.id = next(_ids)

    def __repr__(self):
        return f"Var({self.name}#{self.id})"


@dataclass(frozen=True)
class Struct:
    """An atom (no args) or a compound term like parent(tom, bob)."""

    functor: str
    args: tuple = ()

    def __repr__(self):
        return format_term(self)


NIL = Struct("[]")


def cons(head, tail):
    return Struct(".", (head, tail))


def make_list(items, tail=NIL):
    for item in reversed(items):
        tail = cons(item, tail)
    return tail


# ---------------------------------------------------------------- unification

def walk(t, s):
    """Follow variable bindings until we reach a non-variable or a free var."""
    while isinstance(t, Var) and t in s:
        t = s[t]
    return t


def resolve(t, s):
    """Fully substitute every bound variable inside a term."""
    t = walk(t, s)
    if isinstance(t, Struct) and t.args:
        return Struct(t.functor, tuple(resolve(a, s) for a in t.args))
    return t


def occurs(v, t, s):
    """Occurs check: does variable v appear inside term t? (stops X = f(X))"""
    t = walk(t, s)
    if t is v:
        return True
    if isinstance(t, Struct):
        return any(occurs(v, a, s) for a in t.args)
    return False


def _bind(v, t, s):
    if occurs(v, t, s):
        return None
    s2 = dict(s)
    s2[v] = t
    return s2


def unify(a, b, s):
    """Return an extended substitution that makes a and b equal, or None."""
    a, b = walk(a, s), walk(b, s)
    if a is b:
        return s
    if isinstance(a, Var):
        return _bind(a, b, s)
    if isinstance(b, Var):
        return _bind(b, a, s)
    if isinstance(a, Struct) and isinstance(b, Struct):
        if a.functor != b.functor or len(a.args) != len(b.args):
            return None
        for x, y in zip(a.args, b.args):
            s = unify(x, y, s)
            if s is None:
                return None
        return s
    if type(a) is type(b) and a == b:
        return s
    return None


def rename(t, mapping):
    """Copy a term, replacing each variable with a fresh one (consistently)."""
    if isinstance(t, Var):
        if t not in mapping:
            mapping[t] = Var(t.name)
        return mapping[t]
    if isinstance(t, Struct) and t.args:
        return Struct(t.functor, tuple(rename(a, mapping) for a in t.args))
    return t


@dataclass
class Clause:
    head: Struct
    body: tuple = ()  # empty body = a fact

    def renamed(self):
        mapping = {}
        return rename(self.head, mapping), tuple(rename(g, mapping) for g in self.body)


# ---------------------------------------------------------------- printing

INFIX = {"+", "-", "*", "/", "%", "=", "\\=", "is", "<", ">", "<=", ">=", "==", "!="}


def format_term(t, s=None):
    if s is not None:
        t = walk(t, s)
    if isinstance(t, Var):
        return f"_{t.id}"
    if isinstance(t, bool):
        return "true" if t else "false"
    if isinstance(t, str):
        return '"' + t.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(t, (int, float)):
        return repr(t)
    if isinstance(t, Struct):
        if t.functor == "." and len(t.args) == 2:
            items = []
            while isinstance(t, Struct) and t.functor == "." and len(t.args) == 2:
                items.append(format_term(t.args[0], s))
                t = walk(t.args[1], s) if s is not None else t.args[1]
            inner = ", ".join(items)
            if t == NIL:
                return f"[{inner}]"
            return f"[{inner} | {format_term(t, s)}]"
        if not t.args:
            return t.functor
        if len(t.args) == 2 and t.functor in INFIX:
            return f"{format_term(t.args[0], s)} {t.functor} {format_term(t.args[1], s)}"
        return f"{t.functor}({', '.join(format_term(a, s) for a in t.args)})"
    return repr(t)


# ---------------------------------------------------------------- arithmetic

def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def eval_arith(t, s):
    t = walk(t, s)
    if _number(t):
        return t
    if isinstance(t, Var):
        raise LumiRuntimeError(
            f"arithmetic on unbound variable {t.name} "
            "(give it a value before using 'is' or a comparison)")
    if isinstance(t, Struct):
        if len(t.args) == 2 and t.functor in ("+", "-", "*", "/", "%"):
            a, b = eval_arith(t.args[0], s), eval_arith(t.args[1], s)
            op = t.functor
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if b == 0:
                raise LumiRuntimeError("division by zero")
            if op == "%":
                return a % b
            return a // b if isinstance(a, int) and isinstance(b, int) else a / b
        if len(t.args) == 1 and t.functor == "-":
            return -eval_arith(t.args[0], s)
    raise LumiRuntimeError(f"cannot do arithmetic on {format_term(t, s)}")


# ---------------------------------------------------------------- built-in goals

def _g_true(args, s):
    yield s


def _g_fail(args, s):
    return
    yield  # pragma: no cover  (makes this a generator)


def _g_unify(args, s):
    r = unify(args[0], args[1], s)
    if r is not None:
        yield r


def _g_not_unify(args, s):
    if unify(args[0], args[1], s) is None:
        yield s


def _g_is(args, s):
    r = unify(args[0], eval_arith(args[1], s), s)
    if r is not None:
        yield r


def _g_compare(test):
    def goal(args, s):
        if test(eval_arith(args[0], s), eval_arith(args[1], s)):
            yield s
    return goal


def _g_same(args, s):
    if resolve(args[0], s) == resolve(args[1], s):
        yield s


def _g_not_same(args, s):
    if resolve(args[0], s) != resolve(args[1], s):
        yield s


BUILTIN_GOALS = {
    ("true", 0): _g_true,
    ("fail", 0): _g_fail,
    ("false", 0): _g_fail,
    ("=", 2): _g_unify,
    ("\\=", 2): _g_not_unify,
    ("is", 2): _g_is,
    ("<", 2): _g_compare(lambda a, b: a < b),
    (">", 2): _g_compare(lambda a, b: a > b),
    ("<=", 2): _g_compare(lambda a, b: a <= b),
    (">=", 2): _g_compare(lambda a, b: a >= b),
    ("==", 2): _g_same,
    ("!=", 2): _g_not_same,
}


# ---------------------------------------------------------------- knowledge base

class KnowledgeBase:
    def __init__(self, max_depth=20000):
        self.clauses = {}  # (name, arity) -> [Clause]
        self.max_depth = max_depth

    def add(self, clause):
        key = (clause.head.functor, len(clause.head.args))
        if key in BUILTIN_GOALS:
            raise LumiRuntimeError(f"cannot redefine built-in predicate {key[0]}/{key[1]}")
        self.clauses.setdefault(key, []).append(clause)

    def solve(self, goals, s=None, depth=0):
        """Yield every substitution that makes all goals true (depth-first)."""
        if s is None:
            s = {}
        if depth > self.max_depth:
            raise LumiRuntimeError(
                f"query went deeper than {self.max_depth} steps "
                "(is a rule calling itself forever?)")
        if not goals:
            yield s
            return
        goal, rest = walk(goals[0], s), goals[1:]
        if isinstance(goal, Var):
            raise LumiRuntimeError(f"goal {goal.name} is an unbound variable")
        if not isinstance(goal, Struct):
            raise LumiRuntimeError(f"{format_term(goal)} is not a goal")

        key = (goal.functor, len(goal.args))
        builtin = BUILTIN_GOALS.get(key)
        if builtin is not None:
            for s2 in builtin(goal.args, s):
                yield from self.solve(rest, s2, depth + 1)
            return

        clauses = self.clauses.get(key)
        if clauses is None:
            known = ", ".join(f"{n}/{a}" for n, a in self.clauses) or "none yet"
            raise LumiRuntimeError(
                f"unknown predicate {key[0]}/{key[1]} (known predicates: {known})")
        for clause in list(clauses):
            head, body = clause.renamed()
            s2 = unify(head, goal, s)
            if s2 is not None:
                yield from self.solve(list(body) + list(rest), s2, depth + 1)
