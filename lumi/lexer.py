"""Lexer: turns source text into a list of tokens.

    "let x = 1 + 2"  ->  LET  IDENT(x)  EQ  INT(1)  PLUS  INT(2)  EOF
"""

from .errors import LexError
from .tokens import KEYWORDS, SYMBOLS, T, Token

ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _is_name_char(c):
    return c.isalnum() or c == "_" or c == "'"


def tokenize(source):
    tokens = []
    i, line, col = 0, 1, 1
    n = len(source)
    last_line = 0  # line of the previous token

    def add(type_, text, value, start_line, start_col):
        nonlocal last_line
        tokens.append(Token(type_, text, value, start_line, start_col,
                            first_on_line=start_line != last_line))
        last_line = start_line

    while i < n:
        c = source[i]

        # whitespace
        if c == "\n":
            i, line, col = i + 1, line + 1, 1
            continue
        if c in " \t\r":
            i, col = i + 1, col + 1
            continue

        # comments:  -- until end of line
        if source.startswith("--", i):
            while i < n and source[i] != "\n":
                i += 1
            continue

        start, start_line, start_col = i, line, col

        # numbers:  42   3.14
        if c.isdigit():
            while i < n and source[i].isdigit():
                i += 1
            is_float = i + 1 < n and source[i] == "." and source[i + 1].isdigit()
            if is_float:
                i += 1
                while i < n and source[i].isdigit():
                    i += 1
            text = source[start:i]
            col += i - start
            if is_float:
                add(T.FLOAT, text, float(text), start_line, start_col)
            else:
                add(T.INT, text, int(text), start_line, start_col)
            continue

        # strings:  "hello\n"
        if c == '"':
            i += 1
            chars = []
            while True:
                if i >= n or source[i] == "\n":
                    raise LexError("unterminated string (missing closing \")",
                                   (start_line, start_col))
                ch = source[i]
                if ch == '"':
                    i += 1
                    break
                if ch == "\\":
                    if i + 1 >= n or source[i + 1] not in ESCAPES:
                        raise LexError("unknown escape sequence in string",
                                       (line, col + (i - start)))
                    chars.append(ESCAPES[source[i + 1]])
                    i += 2
                    continue
                chars.append(ch)
                i += 1
            text = source[start:i]
            col += i - start
            add(T.STRING, text, "".join(chars), start_line, start_col)
            continue

        # atom literal:  'bob
        if c == "'":
            i += 1
            if i >= n or not source[i].islower():
                raise LexError("an atom literal must look like 'name "
                               "(quote followed by a lowercase name)",
                               (start_line, start_col))
            while i < n and _is_name_char(source[i]):
                i += 1
            text = source[start:i]
            col += i - start
            add(T.ATOM, text, text[1:], start_line, start_col)
            continue

        # names and keywords
        if c.isalpha() or c == "_":
            while i < n and _is_name_char(source[i]):
                i += 1
            text = source[start:i]
            col += i - start
            if text == "_":
                add(T.UNDERSCORE, text, text, start_line, start_col)
            elif text in KEYWORDS:
                add(KEYWORDS[text], text, text, start_line, start_col)
            elif text[0].isupper() or text[0] == "_":
                add(T.UVAR, text, text, start_line, start_col)
            else:
                add(T.IDENT, text, text, start_line, start_col)
            continue

        # symbols / operators
        for sym, type_ in SYMBOLS:
            if source.startswith(sym, i):
                i += len(sym)
                col += len(sym)
                add(type_, sym, sym, start_line, start_col)
                break
        else:
            raise LexError(f"unexpected character {c!r}", (start_line, start_col))

    tokens.append(Token(T.EOF, "", None, line, col, first_on_line=True))
    return tokens
