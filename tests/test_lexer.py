import pytest

from lumi.errors import LexError
from lumi.lexer import tokenize
from lumi.tokens import T


def types(src):
    return [t.type for t in tokenize(src)][:-1]  # drop EOF


def test_simple_let():
    assert types("let x = 1 + 2") == [T.LET, T.IDENT, T.EQ, T.INT, T.PLUS, T.INT]


def test_comments_are_skipped():
    assert types("x -- this is a comment\ny") == [T.IDENT, T.IDENT]


def test_numbers_and_field_access():
    toks = tokenize("3.14 7 r.Who")
    assert toks[0].type == T.FLOAT and toks[0].value == 3.14
    assert toks[1].type == T.INT and toks[1].value == 7
    assert [t.type for t in toks[2:5]] == [T.IDENT, T.DOT, T.UVAR]


def test_clause_end_dot_after_paren():
    assert types("p(a).") == [T.IDENT, T.LPAREN, T.IDENT, T.RPAREN, T.DOT]


def test_names_variables_atoms():
    assert types("abc Abc _ _Tmp 'bob") == [T.IDENT, T.UVAR, T.UNDERSCORE, T.UVAR, T.ATOM]
    assert tokenize("'bob")[0].value == "bob"


def test_multi_char_operators_win():
    assert types("|> || :: ++ -> => == != <= >= && :- \\=") == [
        T.PIPE, T.OROR, T.CONS, T.CONCAT, T.ARROW, T.FATARROW, T.EQEQ,
        T.NEQ, T.LE, T.GE, T.ANDAND, T.IMPLIED, T.NOTUNIFY]


def test_string_escapes():
    assert tokenize(r'"a\nb\"c"')[0].value == 'a\nb"c'


def test_positions_and_first_on_line():
    toks = tokenize("let x = 1\n  + 2\ny")
    plus, y = toks[4], toks[6]
    assert (plus.line, plus.col, plus.first_on_line) == (2, 3, True)
    assert (y.line, y.col, y.first_on_line) == (3, 1, True)
    assert toks[1].first_on_line is False


def test_unterminated_string():
    with pytest.raises(LexError) as info:
        tokenize('"oops')
    assert info.value.pos == (1, 1)


def test_bad_character():
    with pytest.raises(LexError):
        tokenize("let x = 1 @ 2")
