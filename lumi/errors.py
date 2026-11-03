"""Error types for Lumi.

Every error carries an optional source position ``(line, col)`` so we can
show the user exactly where something went wrong.
"""


class LumiError(Exception):
    kind = "Error"

    def __init__(self, message, pos=None):
        super().__init__(message)
        self.message = message
        self.pos = pos  # (line, col) or None

    def format(self, source=None, filename="<input>"):
        """Return a friendly, multi-line error message with a caret (^)."""
        if self.pos is None:
            return f"{filename}: {self.kind}: {self.message}"
        line, col = self.pos
        text = f"{filename}:{line}:{col}: {self.kind}: {self.message}"
        if source is not None:
            lines = source.splitlines()
            if 1 <= line <= len(lines):
                src_line = lines[line - 1]
                text += f"\n    {src_line}\n    {' ' * (col - 1)}^"
        return text

    def __str__(self):
        return self.format()


class LexError(LumiError):
    kind = "Lex error"


class ParseError(LumiError):
    kind = "Parse error"

    def __init__(self, message, pos=None, at_eof=False):
        super().__init__(message, pos)
        # True when the parser ran out of input. The REPL uses this to
        # know that it should ask for another line instead of failing.
        self.at_eof = at_eof


class LumiRuntimeError(LumiError):
    kind = "Runtime error"
