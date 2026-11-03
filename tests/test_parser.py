import pytest

from lumi import syntax as S
from lumi.errors import ParseError
from lumi.logic import Struct, Var
from lumi.parser import parse


def expr(src):
    stmt = parse(src).statements[0]
    assert isinstance(stmt, S.ExprStmt)
    return stmt.expr


def test_precedence():
    e = expr("1 + 2 * 3")
    assert e == S.BinOp("+", S.Lit(1), S.BinOp("*", S.Lit(2), S.Lit(3)))


def test_application_is_left_associative_and_binds_tighter():
    e = expr("f x y + 1")
    assert e == S.BinOp("+", S.App(S.App(S.Name("f"), S.Name("x")), S.Name("y")), S.Lit(1))


def test_cons_is_right_associative():
    e = expr("1 :: 2 :: []")
    assert e == S.BinOp("::", S.Lit(1), S.BinOp("::", S.Lit(2), S.ListLit([])))


def test_let_function_sugar():
    stmt = parse("let add a b = a + b").statements[0]
    assert stmt == S.LetStmt(
        "add", S.Lambda("a", S.Lambda("b", S.BinOp("+", S.Name("a"), S.Name("b")))))


def test_let_in_expression():
    e = expr("let x = 1 in x")
    assert e == S.Let("x", S.Lit(1), S.Name("x"))


def test_match_arms():
    e = expr("match xs with\n  | [] -> 0\n  | h :: _ -> h")
    assert isinstance(e, S.Match)
    assert e.arms[0][0] == S.PNil()
    assert e.arms[1][0] == S.PCons(S.PVar("h"), S.PWild())


def test_statements_split_on_column_one():
    prog = parse("let x = 1\nprint x\nlet y =\n  2")
    assert [type(s).__name__ for s in prog.statements] == ["LetStmt", "ExprStmt", "LetStmt"]


def test_missing_newline_between_statements_is_an_error():
    with pytest.raises(ParseError):
        parse("let a = 1 let b = 2")


def test_fact_rule_query():
    prog = parse("fact parent(tom, bob).\n"
                 "rule gp(X, Z) :- parent(X, Y), parent(Y, Z).\n"
                 "query gp(tom, W)?")
    fact, rule, query = prog.statements
    assert fact.head == Struct("parent", (Struct("tom"), Struct("bob")))
    # the same variable name inside one clause is the same Var object
    x_in_head = rule.head.args[0]
    x_in_body = rule.body[0].args[0]
    assert isinstance(x_in_head, Var) and x_in_head is x_in_body
    assert [name for name, _ in query.vars] == ["W"]


def test_logic_lists_and_arithmetic():
    rule = parse("rule len([_|T], N) :- len(T, M), N is M + 1.").statements[0]
    first_arg = rule.head.args[0]
    assert first_arg.functor == "." and len(first_arg.args) == 2
    is_goal = rule.body[1]
    assert is_goal.functor == "is" and is_goal.args[1].functor == "+"


def test_several_facts_on_one_line():
    prog = parse("fact p(1). fact p(2).")
    assert len(prog.statements) == 2


def test_incomplete_input_is_flagged_at_eof():
    with pytest.raises(ParseError) as info:
        parse("let f x =")
    assert info.value.at_eof


def test_uppercase_name_in_expression_gives_hint():
    with pytest.raises(ParseError) as info:
        parse("print X")
    assert "logic variables" in info.value.message
