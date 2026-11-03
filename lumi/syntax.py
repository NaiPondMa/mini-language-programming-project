"""AST (abstract syntax tree) node definitions.

The parser builds these; the evaluator walks them. Every node has an
optional ``pos`` = (line, col) for error messages.
"""

from dataclasses import dataclass, field, fields


@dataclass
class Node:
    pos: tuple = field(default=None, kw_only=True, compare=False, repr=False)


# ----------------------------------------------------------------- expressions

@dataclass
class Lit(Node):
    value: object                 # int, float, str, bool, atom (Struct) or UNIT


@dataclass
class Name(Node):
    name: str


@dataclass
class Lambda(Node):
    param: str
    body: Node


@dataclass
class App(Node):
    fn: Node
    arg: Node


@dataclass
class BinOp(Node):
    op: str
    left: Node
    right: Node


@dataclass
class UnaryOp(Node):
    op: str
    operand: Node


@dataclass
class If(Node):
    cond: Node
    then: Node
    else_: Node


@dataclass
class Let(Node):
    name: str
    value: Node
    body: Node
    rec: bool = False


@dataclass
class Match(Node):
    subject: Node
    arms: list                    # [(pattern, expr)]


@dataclass
class ListLit(Node):
    items: list


@dataclass
class TupleLit(Node):
    items: list


@dataclass
class FieldAccess(Node):
    obj: Node
    field: str


@dataclass
class Solve(Node):
    goals: list                   # logic terms
    vars: list                    # [(name, logic Var)] in order of appearance


# ----------------------------------------------------------------- patterns

@dataclass
class PWild(Node):
    pass


@dataclass
class PVar(Node):
    name: str


@dataclass
class PLit(Node):
    value: object


@dataclass
class PNil(Node):
    pass


@dataclass
class PCons(Node):
    head: Node
    tail: Node


@dataclass
class PList(Node):
    items: list


@dataclass
class PTuple(Node):
    items: list


# ----------------------------------------------------------------- statements

@dataclass
class LetStmt(Node):
    name: str
    value: Node
    rec: bool = False


@dataclass
class ExprStmt(Node):
    expr: Node


@dataclass
class FactStmt(Node):
    head: object                  # logic Struct


@dataclass
class RuleStmt(Node):
    head: object
    body: list


@dataclass
class QueryStmt(Node):
    goals: list
    vars: list


@dataclass
class Program(Node):
    statements: list


# ----------------------------------------------------------------- pretty print

def dump(node, indent=0):
    """Readable tree view of an AST (used by `python -m lumi --ast`)."""
    pad = "  " * indent
    if isinstance(node, Node):
        parts = [f"{pad}{type(node).__name__}"]
        for f in fields(node):
            if f.name == "pos":
                continue
            value = getattr(node, f.name)
            if isinstance(value, (Node, list, tuple)) and value:
                parts.append(f"{pad}  {f.name}:")
                parts.append(dump(value, indent + 2))
            else:
                parts.append(f"{pad}  {f.name}: {value!r}")
        return "\n".join(parts)
    if isinstance(node, (list, tuple)):
        return "\n".join(dump(x, indent) for x in node)
    return f"{pad}{node!r}"
