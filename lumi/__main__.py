"""Command line entry point.

    python -m lumi                     start the REPL
    python -m lumi program.lumi        run a file
    python -m lumi program.lumi --tokens   show the tokens (lexer output)
    python -m lumi program.lumi --ast      show the syntax tree (parser output)
"""

import argparse
import sys
from pathlib import Path

from . import __version__, run_with_big_stack
from .errors import LumiError


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lumi", description="Run Lumi programs.")
    ap.add_argument("file", nargs="?", help="a .lumi file (omit to start the REPL)")
    ap.add_argument("--tokens", action="store_true", help="print tokens and stop")
    ap.add_argument("--ast", action="store_true", help="print the syntax tree and stop")
    ap.add_argument("--version", action="version", version=f"lumi {__version__}")
    args = ap.parse_args(argv)

    if args.file is None:
        from .repl import start_repl
        return run_with_big_stack(start_repl)

    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"lumi: cannot read {args.file}: {exc.strerror}", file=sys.stderr)
        return 2

    from .evaluator import Interpreter
    from .lexer import tokenize
    from .parser import parse
    from .syntax import dump

    try:
        if args.tokens:
            for tok in tokenize(source):
                print(repr(tok))
            return 0
        if args.ast:
            print(dump(parse(source)))
            return 0
        run_with_big_stack(Interpreter().run, source)
        return 0
    except LumiError as err:
        sys.stdout.flush()
        print(err.format(source, args.file), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
