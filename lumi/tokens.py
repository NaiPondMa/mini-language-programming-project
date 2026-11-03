"""Token definitions: the 'words' of the Lumi language."""

from dataclasses import dataclass
from enum import Enum, auto


class T(Enum):
    # literals and names
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    IDENT = auto()        # lowercase name:   x, map, parent
    UVAR = auto()         # Uppercase name:   X, Who   (logic variable)
    ATOM = auto()         # quoted atom:      'bob     (atom inside functional code)
    UNDERSCORE = auto()   # _

    # keywords
    LET = auto()
    REC = auto()
    IN = auto()
    FN = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    MATCH = auto()
    WITH = auto()
    TRUE = auto()
    FALSE = auto()
    FACT = auto()
    RULE = auto()
    QUERY = auto()
    SOLVE = auto()
    IS = auto()

    # punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()
    SEMI = auto()
    QUESTION = auto()
    BAR = auto()          # |

    # operators
    ARROW = auto()        # ->
    FATARROW = auto()     # =>
    PIPE = auto()         # |>
    CONS = auto()         # ::
    CONCAT = auto()       # ++
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()           # =
    EQEQ = auto()         # ==
    NEQ = auto()          # !=
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    ANDAND = auto()       # &&
    OROR = auto()         # ||
    NOTUNIFY = auto()     # \=
    IMPLIED = auto()      # :-

    EOF = auto()


KEYWORDS = {
    "let": T.LET,
    "rec": T.REC,
    "in": T.IN,
    "fn": T.FN,
    "if": T.IF,
    "then": T.THEN,
    "else": T.ELSE,
    "match": T.MATCH,
    "with": T.WITH,
    "true": T.TRUE,
    "false": T.FALSE,
    "fact": T.FACT,
    "rule": T.RULE,
    "query": T.QUERY,
    "solve": T.SOLVE,
    "is": T.IS,
}

# Longest symbols first so that "|>" wins over "|".
SYMBOLS = [
    ("|>", T.PIPE), ("||", T.OROR), ("::", T.CONS), ("++", T.CONCAT),
    ("->", T.ARROW), ("=>", T.FATARROW), ("==", T.EQEQ), ("!=", T.NEQ),
    ("<=", T.LE), (">=", T.GE), ("&&", T.ANDAND), (":-", T.IMPLIED),
    ("\\=", T.NOTUNIFY),
    ("(", T.LPAREN), (")", T.RPAREN), ("[", T.LBRACKET), ("]", T.RBRACKET),
    (",", T.COMMA), (".", T.DOT), (";", T.SEMI), ("?", T.QUESTION),
    ("|", T.BAR), ("+", T.PLUS), ("-", T.MINUS), ("*", T.STAR),
    ("/", T.SLASH), ("%", T.PERCENT), ("=", T.EQ), ("<", T.LT), (">", T.GT),
]


@dataclass(frozen=True)
class Token:
    type: T
    text: str
    value: object
    line: int
    col: int
    first_on_line: bool = False  # used for the "new statement at column 1" rule

    def __repr__(self):
        return f"{self.line}:{self.col}\t{self.type.name:<10} {self.text!r}"
