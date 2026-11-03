"""Parser: turns tokens into an AST.

Technique: recursive descent, with *precedence climbing* for binary
operators. Each grammar rule in docs/index.html maps to one method here.

Layout rule: a top-level statement ends when the next token sits at
column 1 of a new line. Indent a line to continue the previous statement.
"""

from . import syntax as S
from .errors import ParseError
from .lexer import tokenize
from .logic import NIL, Struct, Var, make_list
from .tokens import T
from .values import UNIT

# Binary operators: token -> precedence (higher binds tighter).
BINARY_PREC = {
    T.PIPE: 1,
    T.OROR: 2,
    T.ANDAND: 3,
    T.EQEQ: 4, T.NEQ: 4, T.LT: 4, T.GT: 4, T.LE: 4, T.GE: 4,
    T.CONS: 5, T.CONCAT: 5,
    T.PLUS: 6, T.MINUS: 6,
    T.STAR: 7, T.SLASH: 7, T.PERCENT: 7,
}
RIGHT_ASSOC = {T.CONS, T.CONCAT}

# Tokens that can start a function argument:  f 1 "a" x (e) [..]
ARG_START = {T.INT, T.FLOAT, T.STRING, T.TRUE, T.FALSE, T.IDENT, T.ATOM,
             T.LPAREN, T.LBRACKET,
             T.UVAR}  # UVAR only so we can report a helpful error

KEYWORD_EXPR = {T.FN, T.IF, T.MATCH, T.LET, T.SOLVE}

# Relations allowed between two logic terms in a goal.
REL_OPS = {T.EQ: "=", T.NOTUNIFY: "\\=", T.IS: "is", T.LT: "<", T.GT: ">",
           T.LE: "<=", T.GE: ">=", T.EQEQ: "==", T.NEQ: "!="}


def parse(source):
    return Parser(tokenize(source)).parse_program()


def _describe(tok):
    return "end of input" if tok.type == T.EOF else f"'{tok.text}'"


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    # ------------------------------------------------------------ helpers

    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def advance(self):
        tok = self.toks[self.i]
        if tok.type != T.EOF:
            self.i += 1
        return tok

    def check(self, *types):
        return self.peek().type in types

    def match(self, *types):
        return self.advance() if self.check(*types) else None

    def expect(self, type_, what):
        if self.check(type_):
            return self.advance()
        self.error(f"expected {what}, found {_describe(self.peek())}")

    def error(self, message, tok=None):
        tok = tok or self.peek()
        raise ParseError(message, (tok.line, tok.col), at_eof=tok.type == T.EOF)

    def at_boundary(self):
        """True if the next token starts a new top-level statement."""
        tok = self.peek()
        return self.i > 0 and tok.first_on_line and tok.col == 1

    @staticmethod
    def pos(tok):
        return (tok.line, tok.col)

    # ------------------------------------------------------------ program

    def parse_program(self):
        stmts = []
        while True:
            while self.match(T.SEMI):
                pass
            if self.check(T.EOF):
                break
            stmt = self.parse_statement()
            stmts.append(stmt)
            # fact/rule/query end with '.' or '?', so the next one may follow
            # on the same line:   fact p(1). fact p(2).
            ends_itself = isinstance(stmt, (S.FactStmt, S.RuleStmt, S.QueryStmt))
            if not (ends_itself or self.check(T.EOF, T.SEMI) or self.at_boundary()):
                self.error(
                    f"unexpected {_describe(self.peek())} after the end of a statement "
                    "(start each new statement at column 1 of a new line; "
                    "indent lines that continue a statement)")
        return S.Program(stmts, pos=(1, 1))

    def parse_statement(self):
        tok = self.peek()
        p = self.pos(tok)
        if tok.type == T.LET:
            return self.parse_let(top=True)
        if tok.type == T.FACT:
            self.advance()
            head = self.parse_head({})
            self.expect(T.DOT, "'.' at the end of the fact")
            return S.FactStmt(head, pos=p)
        if tok.type == T.RULE:
            self.advance()
            varmap = {}
            head = self.parse_head(varmap)
            self.expect(T.IMPLIED, "':-' after the rule head")
            body = self.parse_goals(varmap)
            self.expect(T.DOT, "'.' at the end of the rule")
            return S.RuleStmt(head, body, pos=p)
        if tok.type == T.QUERY:
            self.advance()
            varmap = {}
            goals = self.parse_goals(varmap)
            self.expect(T.QUESTION, "'?' at the end of the query")
            return S.QueryStmt(goals, list(varmap.items()), pos=p)
        return S.ExprStmt(self.parse_expr(), pos=p)

    def parse_let(self, top):
        let_tok = self.advance()
        p = self.pos(let_tok)
        rec = self.match(T.REC) is not None
        name_tok = self.match(T.IDENT, T.UNDERSCORE)
        if name_tok is None:
            self.error(f"expected a name after 'let', found {_describe(self.peek())}")
        params = []
        while self.check(T.IDENT, T.UNDERSCORE):
            params.append(self.advance())
        self.expect(T.EQ, "'='")
        value = self.parse_expr()
        for param in reversed(params):          # let f x y = e  ==>  fn x => fn y => e
            value = S.Lambda(param.text, value, pos=self.pos(param))
        if self.match(T.IN):
            body = self.parse_expr()
            expr = S.Let(name_tok.text, value, body, rec, pos=p)
            return S.ExprStmt(expr, pos=p) if top else expr
        if top:
            return S.LetStmt(name_tok.text, value, rec, pos=p)
        self.error(f"expected 'in' after a local 'let', found {_describe(self.peek())}")

    # ------------------------------------------------------------ expressions

    def parse_expr(self):
        return self.parse_binary(1)

    def parse_binary(self, min_prec):
        left = self.parse_unary()
        while True:
            tok = self.peek()
            prec = BINARY_PREC.get(tok.type)
            if prec is None or prec < min_prec or self.at_boundary():
                return left
            self.advance()
            next_min = prec if tok.type in RIGHT_ASSOC else prec + 1
            right = self.parse_binary(next_min)
            left = S.BinOp(tok.text, left, right, pos=self.pos(tok))

    def parse_unary(self):
        if self.check(T.MINUS):
            tok = self.advance()
            return S.UnaryOp("-", self.parse_unary(), pos=self.pos(tok))
        return self.parse_application()

    def parse_application(self):
        if self.check(*KEYWORD_EXPR):
            return self.parse_keyword_expr()
        start = self.peek()
        expr = self.parse_postfix()
        while self.check(*ARG_START) and not self.at_boundary():
            arg = self.parse_postfix()
            expr = S.App(expr, arg, pos=self.pos(start))
        return expr

    def parse_postfix(self):
        expr = self.parse_atom()
        while (self.check(T.DOT) and self.peek(1).type in (T.UVAR, T.IDENT)
               and not self.at_boundary()):
            dot = self.advance()
            field = self.advance().text
            expr = S.FieldAccess(expr, field, pos=self.pos(dot))
        return expr

    def parse_atom(self):
        tok = self.peek()
        p = self.pos(tok)
        t = tok.type
        if t in (T.INT, T.FLOAT, T.STRING):
            self.advance()
            return S.Lit(tok.value, pos=p)
        if t in (T.TRUE, T.FALSE):
            self.advance()
            return S.Lit(t == T.TRUE, pos=p)
        if t == T.ATOM:
            self.advance()
            return S.Lit(Struct(tok.value), pos=p)
        if t == T.IDENT:
            self.advance()
            return S.Name(tok.text, pos=p)
        if t == T.LPAREN:
            self.advance()
            if self.match(T.RPAREN):
                return S.Lit(UNIT, pos=p)
            first = self.parse_expr()
            if self.check(T.COMMA):
                items = [first]
                while self.match(T.COMMA):
                    items.append(self.parse_expr())
                self.expect(T.RPAREN, "')' to close the tuple")
                return S.TupleLit(items, pos=p)
            self.expect(T.RPAREN, "')'")
            return first
        if t == T.LBRACKET:
            self.advance()
            items = []
            if not self.check(T.RBRACKET):
                items.append(self.parse_expr())
                while self.match(T.COMMA):
                    items.append(self.parse_expr())
            self.expect(T.RBRACKET, "']' to close the list")
            return S.ListLit(items, pos=p)
        if t in KEYWORD_EXPR:
            return self.parse_keyword_expr()
        if t == T.UVAR:
            self.error(f"'{tok.text}' starts with an uppercase letter, which Lumi reserves "
                       "for logic variables (use them inside fact/rule/query/solve)")
        self.error(f"unexpected {_describe(tok)} (expected an expression)")

    def parse_keyword_expr(self):
        tok = self.peek()
        p = self.pos(tok)
        if tok.type == T.LET:
            return self.parse_let(top=False)
        if tok.type == T.FN:
            self.advance()
            params = []
            while self.check(T.IDENT, T.UNDERSCORE):
                params.append(self.advance().text)
            if not params:
                self.error("expected a parameter name after 'fn'")
            self.expect(T.FATARROW, "'=>' after the parameters")
            body = self.parse_expr()
            for param in reversed(params):
                body = S.Lambda(param, body, pos=p)
            return body
        if tok.type == T.IF:
            self.advance()
            cond = self.parse_expr()
            self.expect(T.THEN, "'then'")
            then = self.parse_expr()
            self.expect(T.ELSE, "'else' (every 'if' needs an 'else')")
            else_ = self.parse_expr()
            return S.If(cond, then, else_, pos=p)
        if tok.type == T.MATCH:
            self.advance()
            subject = self.parse_expr()
            self.expect(T.WITH, "'with'")
            self.match(T.BAR)  # the first '|' is optional
            arms = []
            while True:
                pattern = self.parse_pattern()
                self.expect(T.ARROW, "'->' after the pattern")
                arms.append((pattern, self.parse_expr()))
                if not self.match(T.BAR):
                    break
            return S.Match(subject, arms, pos=p)
        if tok.type == T.SOLVE:
            self.advance()
            varmap = {}
            goals = self.parse_goals(varmap)
            return S.Solve(goals, list(varmap.items()), pos=p)
        self.error(f"unexpected {_describe(tok)}")  # pragma: no cover

    # ------------------------------------------------------------ patterns

    def parse_pattern(self):
        head = self.parse_pattern_atom()
        if self.check(T.CONS):
            tok = self.advance()
            return S.PCons(head, self.parse_pattern(), pos=self.pos(tok))
        return head

    def parse_pattern_atom(self):
        tok = self.peek()
        p = self.pos(tok)
        t = tok.type
        if t == T.UNDERSCORE:
            self.advance()
            return S.PWild(pos=p)
        if t == T.IDENT:
            self.advance()
            return S.PVar(tok.text, pos=p)
        if t in (T.INT, T.FLOAT, T.STRING):
            self.advance()
            return S.PLit(tok.value, pos=p)
        if t == T.MINUS and self.peek(1).type in (T.INT, T.FLOAT):
            self.advance()
            return S.PLit(-self.advance().value, pos=p)
        if t in (T.TRUE, T.FALSE):
            self.advance()
            return S.PLit(t == T.TRUE, pos=p)
        if t == T.ATOM:
            self.advance()
            return S.PLit(Struct(tok.value), pos=p)
        if t == T.LBRACKET:
            self.advance()
            if self.match(T.RBRACKET):
                return S.PNil(pos=p)
            items = [self.parse_pattern()]
            while self.match(T.COMMA):
                items.append(self.parse_pattern())
            self.expect(T.RBRACKET, "']' to close the list pattern")
            return S.PList(items, pos=p)
        if t == T.LPAREN:
            self.advance()
            if self.match(T.RPAREN):
                return S.PLit(UNIT, pos=p)
            first = self.parse_pattern()
            if self.check(T.COMMA):
                items = [first]
                while self.match(T.COMMA):
                    items.append(self.parse_pattern())
                self.expect(T.RPAREN, "')' to close the tuple pattern")
                return S.PTuple(items, pos=p)
            self.expect(T.RPAREN, "')'")
            return first
        self.error(f"unexpected {_describe(tok)} (expected a pattern)")

    # ------------------------------------------------------------ logic terms

    def parse_head(self, varmap):
        tok = self.peek()
        head = self.parse_term(varmap)
        if not isinstance(head, Struct):
            self.error("a fact or rule head must look like name(...) or name", tok)
        return head

    def parse_goals(self, varmap):
        goals = [self.parse_goal(varmap)]
        while self.match(T.COMMA):
            goals.append(self.parse_goal(varmap))
        return goals

    def parse_goal(self, varmap):
        left = self.parse_term(varmap)
        op = REL_OPS.get(self.peek().type)
        if op is not None and not self.at_boundary():
            self.advance()
            return Struct(op, (left, self.parse_term(varmap)))
        return left

    def parse_term(self, varmap):
        left = self.parse_mul_term(varmap)
        while self.check(T.PLUS, T.MINUS) and not self.at_boundary():
            op = self.advance().text
            left = Struct(op, (left, self.parse_mul_term(varmap)))
        return left

    def parse_mul_term(self, varmap):
        left = self.parse_primary_term(varmap)
        while self.check(T.STAR, T.SLASH, T.PERCENT) and not self.at_boundary():
            op = self.advance().text
            left = Struct(op, (left, self.parse_primary_term(varmap)))
        return left

    def parse_primary_term(self, varmap):
        tok = self.peek()
        t = tok.type
        if t == T.UVAR:
            self.advance()
            if tok.text not in varmap:
                varmap[tok.text] = Var(tok.text)
            return varmap[tok.text]
        if t == T.UNDERSCORE:
            self.advance()
            return Var("_")  # every _ is a different variable
        if t in (T.INT, T.FLOAT, T.STRING):
            self.advance()
            return tok.value
        if t == T.MINUS:
            self.advance()
            if self.check(T.INT, T.FLOAT):
                return -self.advance().value
            return Struct("-", (self.parse_primary_term(varmap),))
        if t in (T.TRUE, T.FALSE):
            self.advance()
            return Struct(tok.text)
        if t in (T.IDENT, T.ATOM):
            self.advance()
            name = tok.value
            if self.match(T.LPAREN):
                args = [self.parse_term(varmap)]
                while self.match(T.COMMA):
                    args.append(self.parse_term(varmap))
                self.expect(T.RPAREN, f"')' to close {name}(...)")
                return Struct(name, tuple(args))
            return Struct(name)
        if t == T.LBRACKET:
            self.advance()
            if self.match(T.RBRACKET):
                return NIL
            items = [self.parse_term(varmap)]
            while self.match(T.COMMA):
                items.append(self.parse_term(varmap))
            tail = self.parse_term(varmap) if self.match(T.BAR) else NIL
            self.expect(T.RBRACKET, "']' to close the list")
            return make_list(items, tail)
        if t == T.LPAREN:
            self.advance()
            term = self.parse_term(varmap)
            self.expect(T.RPAREN, "')'")
            return term
        self.error(f"unexpected {_describe(tok)} (expected a logic term such as "
                   "an atom, a Variable, a number or name(...))")
