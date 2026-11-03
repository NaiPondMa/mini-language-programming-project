"""Interactive Read-Eval-Print Loop."""

from . import LANGUAGE_NAME, __version__
from .errors import LumiError, ParseError
from .evaluator import Interpreter

HELP = """\
Type Lumi code and press Enter.
  - If a line is incomplete (e.g. ends with '=' or 'with'), keep typing;
    finish a multi-line input with an empty line.
  - Use ';' to put several statements on one line:  let x = 2; x * x
Commands:
  :help        show this help
  :kb          list known logic predicates
  :quit / :q   leave (or press Ctrl+Z / Ctrl+D)
"""


def start_repl(interp=None):
    interp = interp or Interpreter()
    print(f"{LANGUAGE_NAME} {__version__} - functional + logic. Type :help for help.")
    buffer = []
    while True:
        try:
            line = input("lumi> " if not buffer else "...   ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buffer = []
            continue

        if not buffer:
            cmd = line.strip()
            if cmd in (":q", ":quit"):
                break
            if cmd == ":help":
                print(HELP)
                continue
            if cmd == ":kb":
                for name, arity in interp.kb.clauses:
                    print(f"  {name}/{arity}")
                continue
            if not cmd:
                continue

        # In multi-line mode, wait for an empty line before running.
        if buffer and line.strip():
            buffer.append(line)
            continue
        if not buffer:
            buffer.append(line)

        source = "\n".join(buffer)
        try:
            interp.run(source, repl=True)
            buffer = []
        except ParseError as err:
            if err.at_eof and len(buffer) == 1:
                continue  # incomplete input: ask for more lines
            print(err.format(source, "<repl>"))
            buffer = []
        except LumiError as err:
            print(err.format(source, "<repl>"))
            buffer = []
    return 0
