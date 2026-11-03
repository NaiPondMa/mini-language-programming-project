"""Golden tests: every examples/*.lumi must print exactly examples/expected/*.out.

After changing an example on purpose, regenerate its expected output:
    python -m lumi examples/NAME.lumi > examples/expected/NAME.out
"""

from pathlib import Path

import pytest

from lumi import run

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.lumi")), ids=lambda p: p.stem)
def test_example_output(path):
    expected = (EXAMPLES / "expected" / f"{path.stem}.out").read_text(encoding="utf-8")
    assert run(path.read_text(encoding="utf-8")) == expected.splitlines()
