"""Evaluator: runs an AST.

* Functional side: environments + closures, pattern matching, and
  tail-call optimisation (a `while True` loop instead of a recursive
  Python call when an expression is in tail position).
* Logic side: facts and rules are stored in a KnowledgeBase; `query`
  prints answers and `solve` returns them as a list of records.
"""

import difflib

from . import syntax as S
from .builtins import make_builtins
from .errors import LumiError, LumiRuntimeError
from .logic import NIL, Clause, KnowledgeBase, Struct, Var, format_term, rename, resolve
from .parser import parse
from .values import (UNIT, Builtin, Closure, Record, is_number, show, type_name,
                     values_equal)

QUERY_PRINT_LIMIT = 100   # `query` stops printing after this many answers
SOLVE_LIMIT = 10000       # `solve` refuses to collect more answers than this


class Env:
    """A scope: a dict of names plus a link to the enclosing scope."""

    __slots__ = ("vars", "parent")

    def __init__(self, vars=None, parent=None):
        self.vars = vars if vars is not None else {}
        self.parent = parent

    def lookup(self, name, pos=None):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        hint = difflib.get_close_matches(name, self.all_names(), n=1)
        extra = f" (did you mean '{hint[0]}'?)" if hint else ""
        raise LumiRuntimeError(f"unknown name '{name}'{extra}", pos)

    def define(self, name, value):
        self.vars[name] = value

    def all_names(self):
        names, env = set(), self
        while env is not None:
            names.update(env.vars)
            env = env.parent
        return names


# ------------------------------------------------------------------ helpers

def match_pattern(p, v):
    """Return the variable bindings if value v matches pattern p, else None."""
    if isinstance(p, S.PWild):
        return {}
    if isinstance(p, S.PVar):
        return {p.name: v}
    if isinstance(p, S.PLit):
        return {} if values_equal(p.value, v) else None
    if isinstance(p, S.PNil):
        return {} if isinstance(v, list) and not v else None
    if isinstance(p, S.PCons):
        if not isinstance(v, list) or not v:
            return None
        head = match_pattern(p.head, v[0])
        if head is None:
            return None
        tail = match_pattern(p.tail, v[1:])
        if tail is None:
            return None
        return {**head, **tail}
    if isinstance(p, (S.PList, S.PTuple)):
        kind = list if isinstance(p, S.PList) else tuple
        if not isinstance(v, kind) or len(v) != len(p.items):
            return None
        bindings = {}
        for sub, x in zip(p.items, v):
            b = match_pattern(sub, x)
            if b is None:
                return None
            bindings.update(b)
        return bindings
    raise LumiRuntimeError(f"internal error: unknown pattern {type(p).__name__}")


def binop(op, l, r, pos):
    if op in ("+", "-", "*", "/", "%"):
        if not (is_number(l) and is_number(r)):
            hint = " (use ++ to join strings or lists)" if op == "+" else ""
            raise LumiRuntimeError(
                f"'{op}' needs two numbers, got {type_name(l)} and {type_name(r)}{hint}", pos)
        if op == "+":
            return l + r
        if op == "-":
            return l - r
        if op == "*":
            return l * r
        if r == 0:
            raise LumiRuntimeError("division by zero", pos)
        if op == "%":
            return l % r
        return l // r if isinstance(l, int) and isinstance(r, int) else l / r
    if op == "==":
        return values_equal(l, r)
    if op == "!=":
        return not values_equal(l, r)
    if op in ("<", ">", "<=", ">="):
        if not (is_number(l) and is_number(r) or isinstance(l, str) and isinstance(r, str)):
            raise LumiRuntimeError(
                f"cannot compare {type_name(l)} with {type_name(r)} using '{op}'", pos)
        return {"<": l < r, ">": l > r, "<=": l <= r, ">=": l >= r}[op]
    if op == "::":
        if not isinstance(r, list):
            raise LumiRuntimeError(f"right side of '::' must be a list, got {type_name(r)}", pos)
        return [l] + r
    if op == "++":
        if isinstance(l, list) and isinstance(r, list) or isinstance(l, str) and isinstance(r, str):
            return l + r
        raise LumiRuntimeError(
            f"'++' joins two lists or two strings, got {type_name(l)} and {type_name(r)}", pos)
    raise LumiRuntimeError(f"unknown operator '{op}'", pos)


def term_to_value(t):
    """Convert a (resolved) logic term into a functional value."""
    if isinstance(t, Struct):
        if t.functor == "." and len(t.args) == 2:
            items = []
            while isinstance(t, Struct) and t.functor == "." and len(t.args) == 2:
                items.append(term_to_value(t.args[0]))
                t = t.args[1]
            if t == NIL:
                return items
            return Struct(".", (items[-1], t))  # improper list: leave as a term
        if t == NIL:
            return []
    return t


# ------------------------------------------------------------------ interpreter

class Interpreter:
    def __init__(self, out=None):
        self.out = out or (lambda text: print(text, flush=True))
        self.kb = KnowledgeBase()
        self.globals = Env()
        for name, fn in make_builtins(self).items():
            self.globals.define(name, fn)

    # ---------------------------------------------------------- statements

    def run(self, source, repl=False):
        """Parse and run a whole program. Returns the value of the last statement."""
        program = parse(source)
        result = UNIT
        for stmt in program.statements:
            result = self.execute(stmt, repl)
        return result

    def execute(self, stmt, repl=False):
        try:
            return self._execute(stmt, repl)
        except RecursionError:
            raise LumiRuntimeError(
                "recursion too deep (is a function calling itself forever?)", stmt.pos) from None
        except LumiError as err:
            if err.pos is None:
                err.pos = stmt.pos
            raise

    def _execute(self, stmt, repl):
        if isinstance(stmt, S.LetStmt):
            value = self.eval(stmt.value, self.globals)
            self._name_closure(value, stmt.name)
            self.globals.define(stmt.name, value)
            if repl:
                self.out(f"{stmt.name} = {show(value)}")
            return value
        if isinstance(stmt, S.ExprStmt):
            value = self.eval(stmt.expr, self.globals)
            if repl and value is not UNIT:
                self.out(show(value))
            return value
        if isinstance(stmt, S.FactStmt):
            self.kb.add(Clause(stmt.head, ()))
            return UNIT
        if isinstance(stmt, S.RuleStmt):
            self.kb.add(Clause(stmt.head, tuple(stmt.body)))
            return UNIT
        if isinstance(stmt, S.QueryStmt):
            self.run_query(stmt.goals, stmt.vars)
            return UNIT
        raise LumiRuntimeError(f"internal error: unknown statement {type(stmt).__name__}")

    # ---------------------------------------------------------- logic

    @staticmethod
    def _fresh_goals(goals, vars):
        """Give the goals fresh variables so a query can run many times."""
        mapping = {}
        fresh = [rename(g, mapping) for g in goals]
        named = [(name, mapping.get(v, v)) for name, v in vars if not name.startswith("_")]
        return fresh, named

    def run_query(self, goals, vars):
        goals, named = self._fresh_goals(goals, vars)
        count = 0
        for s in self.kb.solve(goals):
            count += 1
            if not named:
                self.out("true.")
                return
            self.out(", ".join(f"{name} = {format_term(resolve(v, s))}" for name, v in named))
            if count >= QUERY_PRINT_LIMIT:
                self.out(f"... (stopped after {QUERY_PRINT_LIMIT} answers)")
                return
        if count == 0:
            self.out("false.")

    def eval_solve(self, node):
        goals, named = self._fresh_goals(node.goals, node.vars)
        results = []
        for s in self.kb.solve(goals):
            results.append(Record({name: term_to_value(resolve(v, s)) for name, v in named}))
            if len(results) > SOLVE_LIMIT:
                raise LumiRuntimeError(
                    f"solve found more than {SOLVE_LIMIT} answers (infinite answers?)", node.pos)
        return results

    # ---------------------------------------------------------- functions

    @staticmethod
    def _name_closure(value, name):
        if isinstance(value, Closure) and value.name is None:
            value.name = name

    def apply(self, f, arg, pos=None):
        """Call a function value (used by built-ins such as map)."""
        if isinstance(f, Closure):
            return self.eval(f.body, Env({f.param: arg}, f.env))
        return self._call_other(f, arg, pos)

    def _call_other(self, f, arg, pos):
        if isinstance(f, Builtin):
            args = f.args + (arg,)
            if len(args) < f.arity:  # partial application
                return Builtin(f.name, f.arity, f.fn, args)
            try:
                return f.fn(*args)
            except LumiError as err:
                if err.pos is None:
                    err.pos = pos
                raise
        raise LumiRuntimeError(f"cannot call {type_name(f)} {show(f)} like a function", pos)

    # ---------------------------------------------------------- expressions

    def eval(self, e, env):
        # The loop lets tail positions (if branches, match arms, let bodies,
        # function bodies) continue without growing the Python stack.
        while True:
            if isinstance(e, S.Lit):
                return e.value

            if isinstance(e, S.Name):
                return env.lookup(e.name, e.pos)

            if isinstance(e, S.Lambda):
                return Closure(e.param, e.body, env)

            if isinstance(e, S.App):
                f = self.eval(e.fn, env)
                arg = self.eval(e.arg, env)
                if isinstance(f, Closure):
                    e, env = f.body, Env({f.param: arg}, f.env)   # tail call
                    continue
                return self._call_other(f, arg, e.pos)

            if isinstance(e, S.If):
                cond = self.eval(e.cond, env)
                if not isinstance(cond, bool):
                    raise LumiRuntimeError(
                        f"'if' condition must be a bool, got {type_name(cond)}", e.cond.pos)
                e = e.then if cond else e.else_
                continue

            if isinstance(e, S.Let):
                if e.rec:
                    new_env = Env({}, env)
                    value = self.eval(e.value, new_env)
                    new_env.define(e.name, value)
                else:
                    value = self.eval(e.value, env)
                    new_env = Env({e.name: value}, env)
                self._name_closure(value, e.name)
                e, env = e.body, new_env
                continue

            if isinstance(e, S.Match):
                value = self.eval(e.subject, env)
                for pattern, body in e.arms:
                    bindings = match_pattern(pattern, value)
                    if bindings is not None:
                        e, env = body, Env(bindings, env)
                        break
                else:
                    raise LumiRuntimeError(f"no pattern matched the value {show(value)}", e.pos)
                continue

            if isinstance(e, S.BinOp):
                op = e.op
                if op in ("&&", "||"):
                    left = self.eval(e.left, env)
                    if not isinstance(left, bool):
                        raise LumiRuntimeError(f"'{op}' needs bools, got {type_name(left)}", e.pos)
                    if (op == "&&") != left:      # false && _  or  true || _
                        return left
                    right = self.eval(e.right, env)
                    if not isinstance(right, bool):
                        raise LumiRuntimeError(f"'{op}' needs bools, got {type_name(right)}", e.pos)
                    return right
                if op == "|>":                    # x |> f   means   f x
                    arg = self.eval(e.left, env)
                    f = self.eval(e.right, env)
                    if isinstance(f, Closure):
                        e, env = f.body, Env({f.param: arg}, f.env)
                        continue
                    return self._call_other(f, arg, e.pos)
                return binop(op, self.eval(e.left, env), self.eval(e.right, env), e.pos)

            if isinstance(e, S.UnaryOp):
                value = self.eval(e.operand, env)
                if not is_number(value):
                    raise LumiRuntimeError(f"cannot negate {type_name(value)}", e.pos)
                return -value

            if isinstance(e, S.ListLit):
                return [self.eval(x, env) for x in e.items]

            if isinstance(e, S.TupleLit):
                return tuple(self.eval(x, env) for x in e.items)

            if isinstance(e, S.FieldAccess):
                obj = self.eval(e.obj, env)
                if not isinstance(obj, Record):
                    raise LumiRuntimeError(
                        f"'.{e.field}' only works on records from solve, got {type_name(obj)}", e.pos)
                if e.field not in obj.fields:
                    have = ", ".join(obj.fields) or "none"
                    raise LumiRuntimeError(
                        f"record has no field '{e.field}' (fields: {have})", e.pos)
                return obj.fields[e.field]

            if isinstance(e, S.Solve):
                return self.eval_solve(e)

            raise LumiRuntimeError(f"internal error: unknown node {type(e).__name__}")
