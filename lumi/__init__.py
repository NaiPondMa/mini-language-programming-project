"""Lumi: a tiny functional + logic programming language."""

import os
import sys
import threading

LANGUAGE_NAME = "Lumi"
FILE_EXTENSION = ".lumi"
__version__ = "0.1.0"


def run_with_big_stack(fn, *args, stack_mb=200, recursion_limit=50000):
    """Run fn(*args) on a thread with a large stack.

    Recursive interpreters use the Python stack for each nested call, so
    the default limit (1000 frames) is too small for real programs.
    """
    result = {}

    def target():
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(recursion_limit)
        try:
            result["value"] = fn(*args)
        except BaseException as exc:  # re-raised in the caller's thread
            result["error"] = exc
        finally:
            sys.setrecursionlimit(old_limit)

    old_size = threading.stack_size(stack_mb * 1024 * 1024)
    try:
        worker = threading.Thread(target=target, daemon=True)
        worker.start()
    finally:
        threading.stack_size(old_size)
    try:
        while worker.is_alive():
            worker.join(0.1)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        os._exit(130)
    if "error" in result:
        raise result["error"]
    return result.get("value")


def run(source):
    """Run Lumi source code and return the printed lines (handy for tests)."""
    from .evaluator import Interpreter

    lines = []
    run_with_big_stack(Interpreter(out=lines.append).run, source)
    return lines
